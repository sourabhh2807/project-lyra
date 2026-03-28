"""
voice_gen.py — Generates narration audio using edge-tts (Microsoft Neural TTS).
Zero API cost. Runs fully in GitHub Actions runner.
Per-channel voice = brand identity gene.
"""
import os, logging, asyncio, subprocess

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
        self._ensure_edge_tts()

    def synthesize(self, narration_text, slot, video_type):
        """Synthesize narration to WAV file. Returns path or None."""
        if not narration_text or len(narration_text.strip()) < 20:
            log.warning("Narration text too short or empty")
            return None

        # Load channel voice config
        ch_map = self._load_channel_map()
        channel = next((c for c in ch_map["channels"] if c["slot"] == slot), {})
        voice_style = channel.get("voice_style", "authoritative_dramatic")

        # Load genome genes for this slot from learning.json
        learning = self._load_learning()
        wpm_key = str(learning.get("champion_alleles", {}).get("narration_pace_wpm", 155))
        rate = RATE_MAP.get(int(wpm_key) if wpm_key.isdigit() else 155, "0%")

        voice = VOICE_MAP.get(voice_style, VOICE_MAP["default"])
        out_dir = os.path.join(self.root, "creation/voice")
        os.makedirs(out_dir, exist_ok=True)

        ts = self._timestamp()
        mp3_path = os.path.join(out_dir, f"narration_{ts}_slot{slot}_{video_type}.mp3")
        wav_path = mp3_path.replace(".mp3", ".wav")

        try:
            # Write text to temp file to avoid shell escaping issues
            txt_path = os.path.join(out_dir, f"tmp_{ts}.txt")
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(narration_text)

            # Run edge-tts
            cmd = [
                "edge-tts",
                "--voice", voice,
                "--rate", rate,
                "--volume", "+10%",
                "--file", txt_path,
                "--write-media", mp3_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

            # Clean up temp file
            if os.path.exists(txt_path):
                os.remove(txt_path)

            if result.returncode != 0:
                log.error(f"edge-tts failed: {result.stderr}")
                return self._try_async_edge_tts(narration_text, voice, rate, wav_path)

            # Convert mp3 to wav for easier processing
            if os.path.exists(mp3_path):
                convert_cmd = ["ffmpeg", "-y", "-i", mp3_path, "-ar", "44100", "-ac", "1", wav_path]
                subprocess.run(convert_cmd, capture_output=True, timeout=60)
                if os.path.exists(mp3_path):
                    os.remove(mp3_path)

            if os.path.exists(wav_path) and os.path.getsize(wav_path) > 1000:
                log.info(f"Voice generated: {wav_path}")
                return wav_path
            else:
                log.error("Voice file empty or missing")
                return None

        except Exception as e:
            log.error(f"Voice synthesis failed: {e}")
            return None

    def _try_async_edge_tts(self, text, voice, rate, out_path):
        """Async fallback for edge-tts Python API."""
        try:
            import edge_tts
            async def _gen():
                communicate = edge_tts.Communicate(text, voice, rate=rate)
                mp3_tmp = out_path.replace(".wav", "_tmp.mp3")
                await communicate.save(mp3_tmp)
                return mp3_tmp

            mp3_tmp = asyncio.run(_gen())
            if os.path.exists(mp3_tmp):
                convert_cmd = ["ffmpeg", "-y", "-i", mp3_tmp, "-ar", "44100", "-ac", "1", out_path]
                subprocess.run(convert_cmd, capture_output=True, timeout=60)
                os.remove(mp3_tmp)
                if os.path.exists(out_path) and os.path.getsize(out_path) > 1000:
                    return out_path
        except Exception as e:
            log.error(f"Async edge-tts also failed: {e}")
        return None

    def get_duration(self, wav_path):
        """Get audio duration in seconds using ffprobe."""
        try:
            cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                   "-of", "default=noprint_wrappers=1:nokey=1", wav_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            return float(result.stdout.strip())
        except Exception:
            return 0.0

    def _ensure_edge_tts(self):
        try:
            result = subprocess.run(["edge-tts", "--version"], capture_output=True, timeout=5)
            if result.returncode == 0:
                return
        except Exception:
            pass
        log.info("Installing edge-tts...")
        subprocess.run(["pip", "install", "edge-tts", "-q"], timeout=60)

    def _load_channel_map(self):
        with open(os.path.join(self.root, "data/channel_map.json")) as f:
            return json.load(f)

    def _load_learning(self):
        with open(os.path.join(self.root, "data/learning.json")) as f:
            return json.load(f)

    def _timestamp(self):
        from datetime import datetime
        return datetime.now().strftime("%Y%m%d_%H%M%S")


import json
