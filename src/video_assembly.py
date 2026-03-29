"""
video_assembly.py — Assembles images + audio + BGM into final video using FFmpeg.
Handles both long-form (1920x1080 landscape) and shorts (1080x1920 vertical).
Applies Ken Burns effect, text overlays, adaptive pacing, and BGM mixing.
"""
import os, json, subprocess, logging, tempfile, math
from datetime import datetime

log = logging.getLogger("video_assembly")

class VideoAssembler:
    def __init__(self, root):
        self.root = root
        self.render_dir = os.path.join(root, "execution/render")
        os.makedirs(self.render_dir, exist_ok=True)

    def assemble(self, frame_paths, audio_path, scenes, genome, slot, video_type):
        """
        Assemble frames + audio + BGM into a final mp4.
        Returns path to output video or None on failure.
        """
        if not frame_paths or not audio_path:
            log.error("Missing frames or audio — cannot assemble")
            return None

        # Determine output dimensions
        if video_type == "long":
            width, height = 1920, 1080
        else:  # short
            width, height = 1080, 1920

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = os.path.join(self.render_dir,
                                f"video_{ts}_slot{slot}_{video_type}.mp4")

        genes = genome.get("genes", {})
        pacing_profile = genes.get("pacing_profile", "fast_hook_slow_reveal")

        try:
            # Get total audio duration
            audio_duration = self._get_duration(audio_path)
            if audio_duration <= 0:
                log.error(f"Invalid audio duration: {audio_duration}")
                return None

            log.info(f"Assembling {video_type}: {len(frame_paths)} frames, "
                     f"{audio_duration:.1f}s audio, {width}x{height}")

            # Calculate scene durations
            scene_durations = self._calculate_scene_durations(
                scenes, frame_paths, audio_duration, pacing_profile
            )

            # Build FFmpeg complex filtergraph
            success = self._run_ffmpeg(
                frame_paths, audio_path, scene_durations,
                out_path, width, height, scenes, video_type, genes
            )

            if success and os.path.exists(out_path) and os.path.getsize(out_path) > 10000:
                log.info(f"Video assembled: {out_path}")
                return out_path
            else:
                log.error("FFmpeg assembly failed or output file invalid")
                return None

        except Exception as e:
            log.error(f"Assembly crashed: {e}")
            import traceback
            log.debug(traceback.format_exc())
            return None

    def _calculate_scene_durations(self, scenes, frame_paths, total_duration, pacing_profile):
        """Calculate how long each scene/frame should be displayed."""
        n_frames = len(frame_paths)
        if n_frames == 0:
            return []

        # If scenes have estimated durations, use them proportionally
        if scenes and all("duration_estimate_sec" in s for s in scenes[:n_frames]):
            raw = [s["duration_estimate_sec"] for s in scenes[:n_frames]]
            total_raw = sum(raw)
            if total_raw > 0:
                return [total_duration * (d / total_raw) for d in raw]

        # Default: equal distribution with pacing adjustments
        base_dur = total_duration / n_frames

        if pacing_profile == "fast_hook_slow_reveal":
            durations = []
            for i in range(n_frames):
                if i < n_frames * 0.15:      # Hook: fast
                    durations.append(base_dur * 0.6)
                elif i > n_frames * 0.70:    # Payoff: slower
                    durations.append(base_dur * 1.3)
                else:
                    durations.append(base_dur)
            # Normalize to match total duration
            scale = total_duration / sum(durations)
            return [d * scale for d in durations]

        elif pacing_profile == "rapid_fire":
            return [max(2.0, base_dur * 0.7)] * n_frames

        elif pacing_profile == "cinematic":
            return [max(4.0, base_dur * 1.2)] * n_frames

        else:  # constant_medium or default
            return [base_dur] * n_frames

    def _run_ffmpeg(self, frame_paths, audio_path, scene_durations,
                    out_path, width, height, scenes, video_type, genes):
        """Build and run the FFmpeg command."""

        # Ensure we have enough durations
        while len(scene_durations) < len(frame_paths):
            scene_durations.append(scene_durations[-1] if scene_durations else 5.0)

        # Clamp minimum scene duration
        scene_durations = [max(1.5, d) for d in scene_durations]

        # Write concat list for input images
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt',
                                         delete=False, dir=self.render_dir) as f:
            concat_file = f.name
            valid_entries = 0
            for i, (frame, dur) in enumerate(zip(frame_paths, scene_durations)):
                if not os.path.exists(frame):
                    log.warning(f"  Missing frame {i}, skipping")
                    continue
                f.write(f"file '{os.path.abspath(frame)}'\n")
                f.write(f"duration {dur:.3f}\n")
                valid_entries += 1
            # Repeat last frame to avoid truncation
            if valid_entries > 0:
                last_frame = next((fp for fp in reversed(frame_paths)
                                   if os.path.exists(fp)), frame_paths[-1])
                f.write(f"file '{os.path.abspath(last_frame)}'\n")

        if valid_entries == 0:
            log.error("No valid frames for concat — cannot assemble")
            os.unlink(concat_file)
            return False

        # Generate text overlay filter if scenes have overlays
        overlay_filter = self._build_text_overlay_filter(scenes, scene_durations, width, height)

        # BGM path (try to find/use silence if none)
        bgm_path = self._get_bgm(genes.get("bgm_genre", "cinematic_tension"))

        try:
            if bgm_path and os.path.exists(bgm_path):
                # With BGM: mix narration + bgm
                cmd = [
                    "ffmpeg", "-y",
                    "-f", "concat", "-safe", "0", "-i", concat_file,
                    "-i", audio_path,
                    "-i", bgm_path,
                    "-filter_complex",
                    f"[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
                    f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,"
                    f"{self._kenburns_filter(width, height)}[vout];"
                    f"[1:a]volume=1.0[narr];"
                    f"[2:a]volume=0.12,aloop=loop=-1:size=2e+09[bgm];"
                    f"[narr][bgm]amix=inputs=2:duration=first:dropout_transition=3[aout]",
                    "-map", "[vout]", "-map", "[aout]",
                    "-c:v", "libx264", "-preset", "faster", "-crf", "23",
                    "-c:a", "aac", "-b:a", "128k",
                    "-r", "30",
                    "-shortest",
                    "-movflags", "+faststart",
                    out_path
                ]
            else:
                # Without BGM
                cmd = [
                    "ffmpeg", "-y",
                    "-f", "concat", "-safe", "0", "-i", concat_file,
                    "-i", audio_path,
                    "-filter_complex",
                    f"[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
                    f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,"
                    f"{self._kenburns_filter(width, height)}[vout]",
                    "-map", "[vout]", "-map", "1:a",
                    "-c:v", "libx264", "-preset", "faster", "-crf", "23",
                    "-c:a", "aac", "-b:a", "128k",
                    "-r", "30",
                    "-shortest",
                    "-movflags", "+faststart",
                    out_path
                ]

            log.info(f"Running FFmpeg assembly...")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

            if result.returncode != 0:
                log.error(f"FFmpeg error:\n{result.stderr[-2000:]}")
                # Retry with simpler command
                return self._simple_assemble(frame_paths, audio_path, scene_durations,
                                              out_path, width, height)

            return True

        finally:
            try:
                os.unlink(concat_file)
            except Exception:
                pass

    def _simple_assemble(self, frame_paths, audio_path, scene_durations, out_path, w, h):
        """Fallback: simple slideshow without Ken Burns or BGM."""
        log.info("Trying simple FFmpeg assembly as fallback...")

        # Use only the first frame for a single-image video as last resort
        valid_frames = [f for f in frame_paths if os.path.exists(f)]
        if not valid_frames:
            log.error("No valid frames for fallback assembly")
            return False

        first_frame = valid_frames[0]
        audio_dur = self._get_duration(audio_path)

        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", first_frame,
            "-i", audio_path,
            "-vf", f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
                   f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
            "-c:a", "aac", "-b:a", "128k",
            "-t", str(audio_dur),
            "-shortest",
            out_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        return result.returncode == 0

    def _kenburns_filter(self, width, height):
        """Generate a gentle Ken Burns zoom effect for visual dynamism.
        Uses slow zoom in/out cycling every ~10 seconds of output."""
        # Gentle 4% zoom oscillation, no pan drift
        return (f"zoompan=z='1.0+0.04*sin(on/150*PI)':"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                f"d=1:s={width}x{height}:fps=30")

    def _build_text_overlay_filter(self, scenes, durations, width, height):
        """Build drawtext filter for scene text overlays."""
        # For now return empty string — can be enhanced later
        return ""

    def _get_bgm(self, genre):
        """Find BGM file from local library or skip."""
        bgm_dir = os.path.join(self.root, "creation/visuals/bgm")
        if not os.path.exists(bgm_dir):
            return None
        # Look for genre-matching file
        for ext in ["mp3", "wav", "ogg"]:
            candidate = os.path.join(bgm_dir, f"{genre}.{ext}")
            if os.path.exists(candidate):
                return candidate
        # Use any available BGM
        import glob
        files = glob.glob(os.path.join(bgm_dir, "*.mp3"))
        return files[0] if files else None

    def _get_duration(self, path):
        try:
            cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                   "-of", "default=noprint_wrappers=1:nokey=1", path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            return float(result.stdout.strip())
        except Exception:
            return 0.0
