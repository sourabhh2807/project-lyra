"""
voice_gen.py — Generates narration audio using edge-tts (Microsoft Neural TTS).
Zero API cost. Uses Python API directly via asyncio.run().
Per-channel voice = brand identity gene.

V9.1 FIX: Simplified asyncio to always use asyncio.run() (no event loop juggling).
V9.2 FIX: Added text chunking for long scripts (>5000 chars) to prevent WebSocket drops.
           Added retry with backoff. Added detailed error logging for every failure path.
"""
import json
import os
import logging
import asyncio
import subprocess
import time
import re
import tempfile

log = logging.getLogger("voice_gen")

# Voice map per channel slot and style
VOICE_MAP = {
    "authoritative_dramatic": "en-US-GuyNeural",
    "conversational_engaging": "en-US-AriaNeural",
    "teacher_clear": "en-US-BrianNeural",
    "storyteller": "en-US-DavisNeural",
    "provocateur": "en-US-TonyNeural",
    "investigative": "en-US-EricNeural",
    "default": "en-US-GuyNeural"
}

RATE_MAP = {
    130: "-15%", 140: "-10%", 150: "-5%", 155: "+0%",
    160: "+3%", 165: "+5%", 170: "+8%", 180: "+12%", 190: "+15%"
}

# Max chars per edge-tts chunk (prevents WebSocket drops on long texts)
MAX_CHUNK_CHARS = 4500


class VoiceGenerator:
    def __init__(self, root):
        self.root = root

    def synthesize(self, narration_text, slot, video_type):
        """Synthesize narration to audio file. Returns path or None."""
        if not narration_text or len(narration_text.strip()) < 20:
            log.warning(f"Narration text too short or empty (len={len(narration_text) if narration_text else 0})")
            return None

        # Load channel voice config
        ch_map = self._load_channel_map()
        channel = next((c for c in ch_map["channels"] if c["slot"] == slot), {})
        voice_style = channel.get("voice_style", "authoritative_dramatic")

        # Get pace from learning champions
        learning = self._load_learning()
        raw_wpm = learning.get("champion_alleles", {}).get("narration_pace_wpm", 155)
        try:
            wpm_int = int(raw_wpm)
        except (ValueError, TypeError):
            wpm_int = 155
        rate = RATE_MAP.get(wpm_int, "+0%")

        voice = VOICE_MAP.get(voice_style, VOICE_MAP["default"])
        out_dir = os.path.join(self.root, "creation/voice")
        os.makedirs(out_dir, exist_ok=True)

        ts = self._timestamp()
        mp3_path = os.path.join(out_dir, f"narration_{ts}_slot{slot}_{video_type}.mp3")

        text_len = len(narration_text)
        word_count = len(narration_text.split())
        log.info(f"  Voice: {voice} | rate={rate} | {text_len} chars | {word_count} words")

        # Strategy 1: Python edge_tts API (most reliable)
        result = self._synthesize_python_api(narration_text, voice, rate, mp3_path)
        if result:
            return result

        # Strategy 2: edge-tts CLI fallback
        result = self._synthesize_cli(narration_text, voice, rate, mp3_path)
        if result:
            return result

        log.error(f"ALL voice synthesis strategies FAILED for slot {slot} {video_type}")
        return None

    # ── Strategy 1: Python API ────────────────────────────────────────────────

    def _synthesize_python_api(self, text, voice, rate, mp3_path):
        """Use edge_tts Python package. Handles long text via chunking."""
        try:
            import edge_tts
        except ImportError:
            log.warning("edge_tts package not installed — skipping Python API strategy")
            return None

        # For short text: single synthesis call
        if len(text) <= MAX_CHUNK_CHARS:
            return self._synthesize_single(edge_tts, text, voice, rate, mp3_path)

        # For long text: chunk into paragraphs, synthesize each, concatenate with ffmpeg
        log.info(f"  Text is {len(text)} chars — chunking for reliability")
        return self._synthesize_chunked(edge_tts, text, voice, rate, mp3_path)

    def _synthesize_single(self, edge_tts, text, voice, rate, mp3_path, retries=3):
        """Synthesize a single text block with retry logic."""
        for attempt in range(1, retries + 1):
            try:
                async def _generate():
                    communicate = edge_tts.Communicate(text, voice, rate=rate)
                    await communicate.save(mp3_path)

                # Always use asyncio.run() — cleanest pattern, works on Python 3.8+
                asyncio.run(_generate())

                if os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 1000:
                    size = os.path.getsize(mp3_path)
                    log.info(f"  Voice generated via Python API: {size:,} bytes")
                    return mp3_path
                else:
                    size = os.path.getsize(mp3_path) if os.path.exists(mp3_path) else 0
                    log.warning(f"  Attempt {attempt}: file too small ({size} bytes)")

            except Exception as e:
                log.warning(f"  Attempt {attempt}/{retries} failed: {type(e).__name__}: {e}")
                if attempt < retries:
                    wait = 3 * attempt
                    log.info(f"  Retrying in {wait}s...")
                    time.sleep(wait)

        return None

    def _synthesize_chunked(self, edge_tts, text, voice, rate, mp3_path):
        """Split long text into chunks, synthesize each, concat with ffmpeg."""
        chunks = self._split_text(text)
        log.info(f"  Split into {len(chunks)} chunks")

        chunk_paths = []
        tmp_dir = tempfile.mkdtemp(prefix="lyra_voice_")

        try:
            for i, chunk in enumerate(chunks):
                chunk_path = os.path.join(tmp_dir, f"chunk_{i:03d}.mp3")
                log.info(f"  Synthesizing chunk {i+1}/{len(chunks)} ({len(chunk)} chars)...")

                result = self._synthesize_single(edge_tts, chunk, voice, rate, chunk_path, retries=2)
                if result:
                    chunk_paths.append(result)
                else:
                    log.warning(f"  Chunk {i+1} failed — skipping")
                    # Don't abort: partial audio is better than none

                # Brief pause between chunks to avoid rate limits
                if i < len(chunks) - 1:
                    time.sleep(1)

            if not chunk_paths:
                log.error("  All chunks failed — no audio generated")
                return None

            # Single chunk: just move it
            if len(chunk_paths) == 1:
                import shutil
                shutil.move(chunk_paths[0], mp3_path)
                return mp3_path

            # Multiple chunks: concatenate with ffmpeg
            return self._concat_audio(chunk_paths, mp3_path, tmp_dir)

        finally:
            # Cleanup temp files
            import shutil
            try:
                shutil.rmtree(tmp_dir, ignore_errors=True)
            except Exception:
                pass

    def _split_text(self, text):
        """Split text into chunks at sentence boundaries, keeping under MAX_CHUNK_CHARS."""
        # Split on sentence-ending punctuation followed by space
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())

        chunks = []
        current_chunk = ""

        for sentence in sentences:
            if len(current_chunk) + len(sentence) + 1 > MAX_CHUNK_CHARS:
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                current_chunk = sentence
            else:
                current_chunk = f"{current_chunk} {sentence}" if current_chunk else sentence

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        # Safety: if any chunk is still too large, force-split it
        final_chunks = []
        for chunk in chunks:
            if len(chunk) > MAX_CHUNK_CHARS * 1.5:
                # Split at the nearest space around the midpoint
                mid = len(chunk) // 2
                split_idx = chunk.rfind(' ', 0, mid + 200)
                if split_idx == -1:
                    split_idx = mid
                final_chunks.append(chunk[:split_idx].strip())
                final_chunks.append(chunk[split_idx:].strip())
            else:
                final_chunks.append(chunk)

        return [c for c in final_chunks if c.strip()]

    def _concat_audio(self, chunk_paths, output_path, tmp_dir):
        """Concatenate multiple audio files using ffmpeg."""
        concat_list = os.path.join(tmp_dir, "concat.txt")
        with open(concat_list, "w") as f:
            for path in chunk_paths:
                f.write(f"file '{os.path.abspath(path)}'\n")

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", concat_list,
            "-c", "copy",
            output_path
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode == 0 and os.path.exists(output_path):
                size = os.path.getsize(output_path)
                if size > 1000:
                    log.info(f"  Concatenated {len(chunk_paths)} chunks → {size:,} bytes")
                    return output_path
            log.warning(f"  FFmpeg concat failed: {result.stderr[:300]}")
        except Exception as e:
            log.warning(f"  FFmpeg concat error: {e}")

        # Fallback: return first chunk as partial audio
        if chunk_paths:
            import shutil
            shutil.copy2(chunk_paths[0], output_path)
            log.warning(f"  Using first chunk as partial audio fallback")
            return output_path

        return None

    # ── Strategy 2: CLI fallback ──────────────────────────────────────────────

    def _synthesize_cli(self, text, voice, rate, mp3_path):
        """Fallback: use edge-tts command line tool."""
        try:
            out_dir = os.path.dirname(mp3_path)
            txt_path = os.path.join(out_dir, f"tmp_voice_{os.getpid()}.txt")
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(text)

            edge_tts_cmd = self._find_edge_tts()
            if not edge_tts_cmd:
                log.warning("edge-tts CLI not found in PATH or common locations")
                if os.path.exists(txt_path):
                    os.remove(txt_path)
                return None

            cmd = [
                edge_tts_cmd,
                "--voice", voice,
                "--rate", rate,
                "--volume", "+10%",
                "--file", txt_path,
                "--write-media", mp3_path
            ]

            log.info(f"  Trying CLI: {edge_tts_cmd}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if os.path.exists(txt_path):
                os.remove(txt_path)

            if result.returncode != 0:
                log.warning(f"edge-tts CLI exit code {result.returncode}: {result.stderr[:300]}")
                return None

            if os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 1000:
                size = os.path.getsize(mp3_path)
                log.info(f"  Voice generated via CLI: {size:,} bytes")
                return mp3_path

            return None

        except subprocess.TimeoutExpired:
            log.warning("edge-tts CLI timed out after 300s")
            return None
        except Exception as e:
            log.warning(f"CLI synthesis failed: {type(e).__name__}: {e}")
            return None

    def _find_edge_tts(self):
        """Find edge-tts binary in PATH or common pip locations."""
        import shutil
        import glob as g

        # Check PATH first
        found = shutil.which("edge-tts")
        if found:
            return found

        # Check common pip install locations
        search_paths = [
            os.path.expanduser("~/.local/bin/edge-tts"),
            "/usr/local/bin/edge-tts",
            "/opt/hostedtoolcache/Python/3.11.*/x64/bin/edge-tts",
            "/opt/hostedtoolcache/Python/3.12.*/x64/bin/edge-tts",
        ]
        for path in search_paths:
            matches = g.glob(path)
            if matches and os.path.exists(matches[0]):
                return matches[0]

        # Try running as python module
        try:
            result = subprocess.run(
                ["python3", "-m", "edge_tts", "--version"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                return "python3 -m edge_tts"
        except Exception:
            pass

        return None

    # ── Utilities ─────────────────────────────────────────────────────────────

    def get_duration(self, audio_path):
        """Get audio duration in seconds using ffprobe."""
        try:
            cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                   "-of", "default=noprint_wrappers=1:nokey=1", audio_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            return float(result.stdout.strip())
        except Exception:
            return 0.0

    def _load_channel_map(self):
        try:
            with open(os.path.join(self.root, "data/channel_map.json")) as f:
                return json.load(f)
        except Exception:
            return {"channels": []}

    def _load_learning(self):
        try:
            with open(os.path.join(self.root, "data/learning.json")) as f:
                return json.load(f)
        except Exception:
            return {}

    def _timestamp(self):
        from datetime import datetime
        return datetime.now().strftime("%Y%m%d_%H%M%S")
