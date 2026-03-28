"""
voice_gen.py — Generates narration audio using edge-tts (Microsoft Neural TTS).
Zero API cost. Uses Python API directly (no subprocess).
Per-channel voice = brand identity gene.
"""
import json
import os
import logging
import asyncio
import subprocess

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
    130: "-15%", 140: "-10%", 150: "-5%", 155: "0%",
    160: "+3%", 165: "+5%", 170: "+8%", 180: "+12%", 190: "+15%"
}

class VoiceGenerator:
    def __init__(self, root):
        self.root = root

    def synthesize(self, narration_text, slot, video_type):
        """Synthesize narration to audio file. Returns path or None."""
        if not narration_text or len(narration_text.strip()) < 20:
            log.warning("Narration text too short or empty")
            return None

        # Load channel voice config
        ch_map = self._load_channel_map()
        channel = next((c for c in ch_map["channels"] if c["slot"] == slot), {})
        voice_style = channel.get("voice_style", "authoritative_dramatic")

        # Get pace from learning champions
        learning = self._load_learning()
        wpm_key = str(learning.get("champion_alleles", {}).get("narration_pace_wpm", 155))
        rate = RATE_MAP.get(int(wpm_key) if wpm_key.isdigit() else 155, "0%")

        voice = VOICE_MAP.get(voice_style, VOICE_MAP["default"])
        out_dir = os.path.join(self.root, "creation/voice")
        os.makedirs(out_dir, exist_ok=True)

        ts = self._timestamp()
        mp3_path = os.path.join(out_dir, f"narration_{ts}_slot{slot}_{video_type}.mp3")

        log.info(f"  Voice: {voice} rate={rate} text={len(narration_text)} chars")

        # Strategy 1: Python edge_tts API (most reliable)
        result = self._synthesize_python_api(narration_text, voice, rate, mp3_path)
        if result:
            return result

        # Strategy 2: edge-tts CLI
        result = self._synthesize_cli(narration_text, voice, rate, mp3_path)
        if result:
            return result

        log.error("All voice synthesis strategies failed")
        return None

    def _synthesize_python_api(self, text, voice, rate, mp3_path):
        """Use edge_tts Python package directly via asyncio."""
        try:
            import edge_tts

            async def _generate():
                communicate = edge_tts.Communicate(text, voice, rate=rate)
                await communicate.save(mp3_path)

            # Handle event loop - create new or use existing
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # We're in an async context already
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        loop.run_in_executor(pool, lambda: asyncio.run(_generate()))
                else:
                    loop.run_until_complete(_generate())
            except RuntimeError:
                asyncio.run(_generate())

            if os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 1000:
                log.info(f"  Voice generated via Python API: {os.path.getsize(mp3_path)} bytes")
                return mp3_path
            else:
                log.warning("Python API produced empty/small file")
                return None

        except ImportError:
            log.warning("edge_tts Python package not installed, trying CLI")
            return None
        except Exception as e:
            log.warning(f"Python API synthesis failed: {e}")
            return None

    def _synthesize_cli(self, text, voice, rate, mp3_path):
        """Fallback: use edge-tts command line tool."""
        try:
            out_dir = os.path.dirname(mp3_path)
            txt_path = os.path.join(out_dir, f"tmp_voice_{os.getpid()}.txt")
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(text)

            # Try to find edge-tts in common locations
            edge_tts_cmd = self._find_edge_tts()
            if not edge_tts_cmd:
                log.warning("edge-tts CLI not found in PATH")
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
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)

            if os.path.exists(txt_path):
                os.remove(txt_path)

            if result.returncode != 0:
                log.warning(f"edge-tts CLI failed: {result.stderr[:200]}")
                return None

            if os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 1000:
                log.info(f"  Voice generated via CLI: {os.path.getsize(mp3_path)} bytes")
                return mp3_path

            return None

        except Exception as e:
            log.warning(f"CLI synthesis failed: {e}")
            return None

    def _find_edge_tts(self):
        """Find edge-tts binary in PATH or common pip locations."""
        import shutil
        # Check PATH
        found = shutil.which("edge-tts")
        if found:
            return found
        # Check common pip install locations
        for path in [
            os.path.expanduser("~/.local/bin/edge-tts"),
            "/usr/local/bin/edge-tts",
            "/opt/hostedtoolcache/Python/3.11.*/x64/bin/edge-tts",
        ]:
            import glob as g
            matches = g.glob(path)
            if matches and os.path.exists(matches[0]):
                return matches[0]
        return None

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
