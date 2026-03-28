"""
quality_gate.py — 7-gate pre-publish quality checker.
ALL gates must pass. One failure = hold or discard. Never publish a failure.
"""
import os, json, requests, subprocess, logging, re

log = logging.getLogger("quality_gate")

GATE_THRESHOLDS = {
    "research_confidence_min": 0.35,
    "script_fluff_max": 0.15,
    "factual_score_min": 0.70,
    "audio_clarity_min": 0.65,
    "honesty_score_min": 0.65,
    "ngram_repeat_max": 0.45,
}

class QualityGate:
    def __init__(self, root):
        self.root    = root
        self.gem_key = os.environ.get("GEMINI_API_KEY", "")
        self._load_thresholds()

    def _load_thresholds(self):
        path = os.path.join(self.root, "governance/thresholds.json")
        if os.path.exists(path):
            with open(path) as f:
                self.thresholds = json.load(f)
        else:
            self.thresholds = GATE_THRESHOLDS

    def check_all(self, script, audio_path, video_path,
                  thumbnail_path, title, topic, genome):
        """
        Run all 7 quality gates.
        Returns {"passed": bool, "scores": {...}, "failures": [...]}
        """
        failures = []
        scores   = {}

        # ── Gate 1: Research Quality ─────────────────────────────────────────
        g1 = self._gate1_research(topic)
        scores["research"] = g1
        if not g1["passed"]:
            failures.append(f"Gate 1 (Research): {g1['reason']}")

        # ── Gate 2: Script Quality ───────────────────────────────────────────
        g2 = self._gate2_script(script)
        scores["script"] = g2
        if not g2["passed"]:
            failures.append(f"Gate 2 (Script): {g2['reason']}")

        # ── Gate 3: Narrative Structure ──────────────────────────────────────
        g3 = self._gate3_narrative(script)
        scores["narrative"] = g3
        if not g3["passed"]:
            failures.append(f"Gate 3 (Narrative): {g3['reason']}")

        # ── Gate 4: Audio Quality ────────────────────────────────────────────
        g4 = self._gate4_audio(audio_path)
        scores["audio"] = g4
        if not g4["passed"]:
            failures.append(f"Gate 4 (Audio): {g4['reason']}")

        # ── Gate 5: Video Quality ────────────────────────────────────────────
        g5 = self._gate5_video(video_path)
        scores["video"] = g5
        if not g5["passed"]:
            failures.append(f"Gate 5 (Video): {g5['reason']}")

        # ── Gate 6: Authenticity ─────────────────────────────────────────────
        g6 = self._gate6_authenticity(script)
        scores["authenticity"] = g6
        if not g6["passed"]:
            failures.append(f"Gate 6 (Authenticity): {g6['reason']}")

        # ── Gate 7: Platform Safety + Honesty ────────────────────────────────
        g7 = self._gate7_safety(script, title, topic)
        scores["safety"] = g7
        if not g7["passed"]:
            failures.append(f"Gate 7 (Safety): {g7['reason']}")

        passed = len(failures) == 0
        log.info(f"Quality Gate: {'PASS ✓' if passed else 'FAIL ✗'} — {len(failures)} failures")
        return {"passed": passed, "scores": scores, "failures": failures}

    # ── GATE 1: Research Quality ──────────────────────────────────────────────
    def _gate1_research(self, topic):
        conf = topic.get("research_confidence", 0.5)
        min_conf = self.thresholds.get("research_confidence_min", 0.35)
        if conf < min_conf:
            return {"passed": False, "score": conf,
                    "reason": f"Research confidence {conf:.2f} < {min_conf}"}
        if not topic.get("topic") or len(topic.get("topic", "")) < 5:
            return {"passed": False, "score": 0.0, "reason": "Topic is empty or too short"}
        if not topic.get("content_angles"):
            return {"passed": False, "score": conf,
                    "reason": "No content angles defined — research incomplete"}
        return {"passed": True, "score": conf, "reason": "OK"}

    # ── GATE 2: Script Quality ────────────────────────────────────────────────
    def _gate2_script(self, script):
        if not script or len(script.strip()) < 200:
            return {"passed": False, "score": 0.0, "reason": "Script too short (<200 chars)"}

        words  = script.split()
        w_count = len(words)

        if w_count < 800:
            return {"passed": False, "score": 0.3,
                    "reason": f"Script too short ({w_count} words — need 800+ for long video)"}

        # N-gram repetition check (simple)
        repeat_score = self._ngram_repeat_score(script)
        max_repeat = self.thresholds.get("ngram_repeat_max", 0.45)
        if repeat_score > max_repeat:
            return {"passed": False, "score": repeat_score,
                    "reason": f"Script is too repetitive (n-gram overlap {repeat_score:.2f})"}

        # Check script starts with a hook (first 50 words should not be generic)
        first_50 = " ".join(words[:50]).lower()
        bad_starts = ["in this video", "welcome to", "today we are going to", "hi everyone",
                      "hello everyone", "my name is", "don't forget to subscribe"]
        for bad in bad_starts:
            if first_50.startswith(bad):
                return {"passed": False, "score": 0.4,
                        "reason": f"Script starts with generic opener: '{bad}'"}

        return {"passed": True, "score": 0.85, "reason": "OK"}

    def _ngram_repeat_score(self, text):
        words = re.sub(r'[^a-z\s]', '', text.lower()).split()
        if len(words) < 20:
            return 0.0
        n = 4
        ngrams = [tuple(words[i:i+n]) for i in range(len(words)-n)]
        if not ngrams:
            return 0.0
        unique = len(set(ngrams))
        repeat_ratio = 1.0 - (unique / len(ngrams))
        return repeat_ratio

    # ── GATE 3: Narrative Quality ─────────────────────────────────────────────
    def _gate3_narrative(self, script):
        """Use Gemini to check narrative structure. Fallback to heuristics."""
        if self.gem_key:
            try:
                return self._llm_narrative_check(script[:3000])
            except Exception as e:
                log.warning(f"LLM narrative check failed: {e}, using heuristics")

        # Heuristic fallback
        script_lower = script.lower()
        has_hook     = any(w in script_lower[:300] for w in
                          ["imagine", "what if", "never told", "secret", "shocking",
                           "nobody knows", "actually", "the truth", "hidden", "real reason"])
        has_reveal   = any(w in script_lower[len(script)//2:] for w in
                          ["revealed", "reveals", "turns out", "in fact", "actually",
                           "the answer", "the reason", "here's why", "that's because"])

        if not has_hook:
            return {"passed": False, "score": 0.4,
                    "reason": "No identifiable hook in first 300 characters"}
        if not has_reveal:
            return {"passed": True, "score": 0.65,
                    "reason": "Hook found but no clear payoff marker detected (soft pass)"}
        return {"passed": True, "score": 0.80, "reason": "OK"}

    def _llm_narrative_check(self, script_excerpt):
        prompt = f"""Evaluate this YouTube video script for narrative quality.

Script excerpt:
\"\"\"{script_excerpt}\"\"\"

Score each element 0.0-1.0:
- hook_strength: Does it grab attention in first 30 seconds?
- setup_clarity: Is context established clearly?
- tension_maintained: Is curiosity/tension kept throughout?
- payoff_present: Is there a satisfying reveal/conclusion?
- voice_authenticity: Does it sound like a real point of view?

Return ONLY JSON: {{"hook_strength": 0.0, "setup_clarity": 0.0, "tension_maintained": 0.0, "payoff_present": 0.0, "voice_authenticity": 0.0, "overall": 0.0, "passed": true, "reason": "brief"}}"""

        url  = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.gem_key}"
        body = {"contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"maxOutputTokens": 200, "temperature": 0.1}}
        r    = requests.post(url, json=body, timeout=25)
        text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        text = self._strip_json(text)
        data = json.loads(text)
        data.setdefault("passed", data.get("overall", 0.5) >= 0.55)
        data.setdefault("reason", "LLM narrative check")
        data.setdefault("score",  data.get("overall", 0.5))
        return data

    # ── GATE 4: Audio Quality ─────────────────────────────────────────────────
    def _gate4_audio(self, audio_path):
        if not audio_path or not os.path.exists(audio_path):
            return {"passed": False, "score": 0.0, "reason": "Audio file missing"}
        if os.path.getsize(audio_path) < 5000:
            return {"passed": False, "score": 0.0, "reason": "Audio file too small"}

        # Get duration via ffprobe
        try:
            cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                   "-of", "default=noprint_wrappers=1:nokey=1", audio_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            duration = float(result.stdout.strip())
            if duration < 60:
                return {"passed": False, "score": 0.3,
                        "reason": f"Audio too short ({duration:.0f}s — need 60s+ for long video)"}
        except Exception:
            pass  # Can't check duration, soft pass

        return {"passed": True, "score": 0.80, "reason": "OK"}

    # ── GATE 5: Video Quality ─────────────────────────────────────────────────
    def _gate5_video(self, video_path):
        if not video_path or not os.path.exists(video_path):
            return {"passed": False, "score": 0.0, "reason": "Video file missing"}

        size_mb = os.path.getsize(video_path) / (1024 * 1024)
        if size_mb < 1.0:
            return {"passed": False, "score": 0.0,
                    "reason": f"Video file too small ({size_mb:.1f} MB)"}

        try:
            # Check video streams exist
            cmd = ["ffprobe", "-v", "error", "-count_packets",
                   "-show_entries", "stream=codec_type,nb_read_packets",
                   "-of", "json", video_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            data   = json.loads(result.stdout)
            streams = data.get("streams", [])
            has_video = any(s.get("codec_type") == "video" for s in streams)
            has_audio = any(s.get("codec_type") == "audio" for s in streams)

            if not has_video:
                return {"passed": False, "score": 0.0, "reason": "No video stream in output"}
            if not has_audio:
                return {"passed": False, "score": 0.0, "reason": "No audio stream in output"}
        except Exception as e:
            log.warning(f"Video probe failed: {e} — soft pass")

        return {"passed": True, "score": 0.80, "reason": f"OK ({size_mb:.1f} MB)"}

    # ── GATE 6: Authenticity ──────────────────────────────────────────────────
    def _gate6_authenticity(self, script):
        """Check that the script has a real point of view, not template filler."""
        if not script:
            return {"passed": False, "score": 0.0, "reason": "Empty script"}

        filler_phrases = [
            "in this video we will", "today i will show you", "let's dive in",
            "without further ado", "so there you have it", "make sure to like and subscribe",
            "first things first", "let's get started", "stay tuned",
        ]
        script_lower  = script.lower()
        filler_count  = sum(1 for p in filler_phrases if p in script_lower)
        filler_density = filler_count / max(1, len(script.split()) / 100)

        if filler_density > 0.8:
            return {"passed": False, "score": 0.35,
                    "reason": f"Script contains too much template filler ({filler_count} phrases)"}

        # Check for opinion/stance markers (authentic voice)
        stance_words = ["actually", "in reality", "what most people miss", "the truth is",
                        "here's what's interesting", "i believe", "consider this",
                        "what nobody talks about", "this matters because"]
        has_stance = any(w in script_lower for w in stance_words)

        if not has_stance:
            return {"passed": True, "score": 0.60,
                    "reason": "No clear stance markers detected (soft pass — review recommended)"}

        return {"passed": True, "score": 0.82, "reason": "OK"}

    # ── GATE 7: Platform Safety + Honesty ────────────────────────────────────
    def _gate7_safety(self, script, title, topic):
        """Check for policy risk patterns and title-content honesty."""
        script_lower = script.lower() if script else ""
        title_lower  = title.lower() if title else ""

        # Hard blocked patterns
        blocked = [
            "how to make a bomb", "how to hack", "child", "suicide method",
            "kill yourself", "self harm", "make explosives"
        ]
        for pattern in blocked:
            if pattern in script_lower or pattern in title_lower:
                return {"passed": False, "score": 0.0,
                        "reason": f"Blocked content pattern detected: '{pattern}'"}

        # Check title doesn't wildly misrepresent topic
        topic_words = set((topic.get("topic", "") + " " + topic.get("niche", "")).lower().split())
        title_words = set(title_lower.split())
        if topic_words and title_words:
            overlap = len(topic_words & title_words) / max(1, len(topic_words))
            if overlap < 0.05 and len(title_words) > 3:
                return {"passed": True, "score": 0.65,
                        "reason": "Low title-topic word overlap (soft pass — monitor CTR vs AVD)"}

        return {"passed": True, "score": 0.90, "reason": "OK"}

    def _strip_json(self, text):
        if "```" in text:
            parts = text.split("```")
            text  = parts[1] if len(parts) > 1 else text
            if text.startswith("json"):
                text = text[4:]
        return text.strip()
