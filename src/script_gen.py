"""
script_gen.py — Generates long video scripts (10-15 min) and shorts scripts (45-59 sec)
using Gemini 1.5 Flash. Returns structured scene data for downstream assembly.
"""
import json, os, requests, logging, uuid
from datetime import datetime, timezone

log = logging.getLogger("script_gen")

class ScriptGenerator:
    def __init__(self, root):
        self.root = root
        self.gemini_key = os.environ.get("GEMINI_API_KEY", "")
        self.groq_key   = os.environ.get("GROQ_API_KEY", "")

    def generate(self, topic, genome, channel_config):
        """Generate both long and short scripts. Returns dict or None on failure."""
        niche  = genome["niche"]
        genes  = genome["genes"]

        long_prompt  = self._build_long_prompt(topic, genes, channel_config)
        short_prompt = self._build_short_prompt(topic, genes, channel_config)

        try:
            log.info(f"Generating LONG script for: {topic['topic']}")
            long_raw  = self._call_llm(long_prompt, max_tokens=3500)
            long_data = json.loads(long_raw)

            log.info(f"Generating SHORTS script for: {topic['topic']}")
            short_raw  = self._call_llm(short_prompt, max_tokens=800)
            short_data = json.loads(short_raw)

            # Save raw scripts to disk
            script_id = str(uuid.uuid4())[:8]
            self._save_script(script_id, "long", long_data)
            self._save_script(script_id, "short", short_data)

            return {
                "script_id": script_id,
                "long_script": long_data.get("full_narration", ""),
                "long_scenes": long_data.get("scenes", []),
                "shorts_script": short_data.get("full_narration", ""),
                "short_scenes": short_data.get("scenes", []),
                "thumbnail_text": long_data.get("thumbnail_text", topic["topic"][:25]),
                "title_candidates": long_data.get("title_candidates", []),
                "tags_suggested": long_data.get("tags", []),
            }

        except Exception as e:
            log.error(f"Script generation failed: {e}")
            return None

    # ── prompt builders ───────────────────────────────────────────────────────

    def _build_long_prompt(self, topic, genes, ch):
        niche_cfg = self._load_niche(ch["niche"])
        target_min = ch.get("long_video_target_min", 10)
        target_max = ch.get("long_video_target_max", 15)
        target_wpm = genes.get("narration_pace_wpm", 155)
        target_words = int(((target_min + target_max) / 2) * target_wpm)

        hook_type   = genes.get("hook_type", "curiosity_gap")
        narrative   = genes.get("narrative_structure", "documentary_reveal")
        narr_style  = genes.get("narration_style", "authoritative_dramatic")
        payoff_pct  = genes.get("payoff_placement_pct", 0.70)
        open_loops  = genes.get("open_loop_count", 2)
        explanation = genes.get("explanation_depth", "medium")
        citations   = genes.get("source_citation_density", "light")
        pacing      = genes.get("pacing_profile", "fast_hook_slow_reveal")

        return f"""You are a world-class YouTube scriptwriter for the channel "{ch['name']}" in the "{niche_cfg.get('display_name', ch['niche'])}" niche.

TOPIC: {topic['topic']}
WHY NOW: {topic.get('why_now', 'Currently trending and highly relevant')}
AUDIENCE STATE: {topic.get('audience_state', 'entertainment-seeking')}
HOOK TYPE: {hook_type}
NARRATIVE STRUCTURE: {narrative}
NARRATION STYLE: {narr_style}
TARGET LENGTH: {target_min}-{target_max} minutes ({target_words} words approximately)
PAYOFF PLACEMENT: Main reveal at {int(payoff_pct * 100)}% through the video
OPEN LOOPS: Plant {open_loops} unresolved tension threads in the hook
EXPLANATION DEPTH: {explanation}
SOURCE CITATIONS: {citations} (mention real sources when relevant)
PACING PROFILE: {pacing}
AUDIENCE IDENTITY: {niche_cfg.get('identity_archetype', 'curious truth-seekers')}
EMOTIONAL TRIGGER: {topic.get('trigger_type_recommended', 'curiosity_gap')}

STRUCTURE REQUIREMENTS:
- HOOK (first 30 seconds): Must use {hook_type}. Must open {open_loops} tension loop(s). Must make a clear, fulfillable promise.
- SETUP: Establish why this matters. Give context without revealing the main payoff.
- ESCALATION: Build tension. Reveal supporting facts. Keep at least one major loop open.
- REVEAL/PAYOFF (around {int(payoff_pct * 100)}% mark): Deliver the main promise. Slightly exceed expectations.
- CLOSE: Either resolve all loops cleanly OR open one future loop to drive subscriptions.

QUALITY RULES:
- No filler sentences. Every sentence must serve the promise.
- No jargon without immediate clear explanation.
- No robotic transitions ("In this video we will..." is forbidden).
- The hook must work WITHOUT visuals — it must work as audio alone.
- The payoff must feel genuinely satisfying, not anticlimactic.
- Write as a confident, knowledgeable narrator with a distinct point of view.

Return ONLY valid JSON (no markdown, no explanation):
{{
  "title_candidates": ["title 1", "title 2", "title 3"],
  "thumbnail_text": "MAX 4 WORDS FOR THUMBNAIL",
  "full_narration": "complete narration text {target_words} words, no scene labels",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8"],
  "scenes": [
    {{
      "scene_id": 1,
      "duration_estimate_sec": 25,
      "narration": "The exact narration text for this scene",
      "visual_description": "Detailed description of what to show: specific scene, mood, colors, composition",
      "text_overlay": "Short text to show on screen (optional, max 6 words, or empty string)",
      "intensity": "high | medium | low",
      "pacing": "fast | medium | slow"
    }}
  ]
}}

Make sure scenes cover the full video length with approximately {target_words // 20} scenes total."""

    def _build_short_prompt(self, topic, genes, ch):
        niche_cfg = self._load_niche(ch["niche"])
        hook_type = genes.get("hook_type", "curiosity_gap")
        narr_style = genes.get("narration_style", "authoritative_dramatic")

        return f"""You are a YouTube Shorts scriptwriter for "{ch['name']}" in the "{niche_cfg.get('display_name', ch['niche'])}" niche.

Create a VERTICAL SHORT (45-58 seconds) based on this topic:
TOPIC: {topic['topic']}
HOOK TYPE: {hook_type}
NARRATION STYLE: {narr_style}
TARGET WORDS: 130-160 words (for 45-58 seconds at 160-170 wpm)

SHORTS STRUCTURE (strict):
- Seconds 0-5: HOOK. One shocking statement or curiosity gap. No intro, no channel name.
- Seconds 5-40: RAPID PAYOFF. Deliver value fast. 3-4 key points. Each one a revelation.
- Seconds 40-55: CLOSE. Punch line or surprising final fact. End with a cliffhanger or call to subscribe.

RULES:
- First word must grab attention. Do NOT start with "In", "Today", "Hi", "Welcome".
- Every sentence must earn its place. Zero filler.
- Speak directly to the viewer (use "you").
- Vertical video: visuals are simple, text-driven.

Return ONLY valid JSON:
{{
  "shorts_title": "Shorts title under 60 characters with hook",
  "full_narration": "complete 130-160 word narration text",
  "scenes": [
    {{
      "scene_id": 1,
      "duration_estimate_sec": 8,
      "narration": "narration text for this scene",
      "visual_description": "simple, bold visual: e.g. dark background with glowing text",
      "text_overlay": "bold hook text on screen",
      "intensity": "high",
      "pacing": "fast"
    }}
  ]
}}"""

    # ── LLM call with fallback ────────────────────────────────────────────────

    def _call_llm(self, prompt, max_tokens=3000):
        """Call Gemini, fallback to Groq on failure."""
        try:
            return self._call_gemini(prompt, max_tokens)
        except Exception as e:
            log.warning(f"Gemini failed ({e}), trying Groq fallback")
            return self._call_groq(prompt, max_tokens)

    def _call_gemini(self, prompt, max_tokens):
        if not self.gemini_key:
            raise ValueError("GEMINI_API_KEY not set")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.gemini_key}"
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.8}
        }
        r = requests.post(url, json=body, timeout=60)
        r.raise_for_status()
        text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        return self._clean_json(text)

    def _call_groq(self, prompt, max_tokens):
        if not self.groq_key:
            raise ValueError("GROQ_API_KEY not set")
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self.groq_key}", "Content-Type": "application/json"}
        body = {
            "model": "llama3-8b-8192",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.8
        }
        r = requests.post(url, json=body, headers=headers, timeout=60)
        r.raise_for_status()
        text = r.json()["choices"][0]["message"]["content"].strip()
        return self._clean_json(text)

    def _clean_json(self, text):
        if text.startswith("```"):
            parts = text.split("```")
            text = parts[1] if len(parts) > 1 else text
            if text.startswith("json"):
                text = text[4:]
        return text.strip()

    def _save_script(self, script_id, video_type, data):
        fname = f"script_{script_id}_{video_type}.json"
        path = os.path.join(self.root, f"creation/scripts/{fname}")
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def _load_niche(self, niche):
        with open(os.path.join(self.root, "data/niche_config.json")) as f:
            return json.load(f)["niches"].get(niche, {})
