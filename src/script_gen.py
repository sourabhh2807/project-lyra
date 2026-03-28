"""
script_gen.py — Generates long video scripts (10-15 min) and shorts scripts (45-59 sec)
using Gemini 1.5 Flash. Returns structured scene data for downstream assembly.
"""
import json, os, re, requests, logging, uuid
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
            long_raw  = self._call_llm(long_prompt, max_tokens=4000)
            if not long_raw:
                log.error("LLM returned empty response for long script")
                return None
            long_data = self._safe_parse_json(long_raw, "long")
            if not long_data:
                log.error(f"Failed to parse long script JSON. Raw (first 500 chars): {long_raw[:500]}")
                return None

            log.info(f"Generating SHORTS script for: {topic['topic']}")
            short_raw  = self._call_llm(short_prompt, max_tokens=1200)
            if not short_raw:
                log.error("LLM returned empty response for shorts script")
                # Continue with long only — shorts are optional
                short_data = {"full_narration": "", "scenes": []}
            else:
                short_data = self._safe_parse_json(short_raw, "short")
                if not short_data:
                    log.warning("Failed to parse shorts JSON, continuing with long only")
                    short_data = {"full_narration": "", "scenes": []}

            # Save raw scripts to disk
            script_id = str(uuid.uuid4())[:8]
            self._save_script(script_id, "long", long_data)
            if short_data.get("scenes"):
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
            import traceback
            log.error(traceback.format_exc())
            return None

    # ── robust JSON parsing ──────────────────────────────────────────────────

    def _safe_parse_json(self, text, label=""):
        """Try multiple strategies to extract valid JSON from LLM output."""
        if not text:
            return None

        # Strategy 1: Direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Strategy 2: Strip markdown fences (```json ... ```)
        cleaned = self._strip_markdown_fences(text)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # Strategy 3: Find the first { ... } block using brace matching
        extracted = self._extract_json_object(text)
        if extracted:
            try:
                return json.loads(extracted)
            except json.JSONDecodeError:
                pass

        # Strategy 4: Try to find JSON between first { and last }
        first_brace = text.find('{')
        last_brace = text.rfind('}')
        if first_brace != -1 and last_brace > first_brace:
            attempt = text[first_brace:last_brace + 1]
            try:
                return json.loads(attempt)
            except json.JSONDecodeError:
                pass

        # Strategy 5: Remove common LLM prefixes/suffixes and retry
        for prefix in ["Here is the JSON:", "Here's the output:", "Here is the result:", "Output:", "Response:"]:
            if prefix.lower() in text.lower():
                idx = text.lower().index(prefix.lower()) + len(prefix)
                attempt = text[idx:].strip()
                try:
                    return json.loads(attempt)
                except json.JSONDecodeError:
                    # Try extracting from this substring
                    sub = self._extract_json_object(attempt)
                    if sub:
                        try:
                            return json.loads(sub)
                        except json.JSONDecodeError:
                            pass

        log.error(f"All JSON parse strategies failed for {label}")
        return None

    def _strip_markdown_fences(self, text):
        """Remove ```json ... ``` or ``` ... ``` wrappers."""
        text = text.strip()
        # Pattern: ```json\n...\n```  or  ```\n...\n```
        pattern = r'```(?:json)?\s*\n?(.*?)\n?\s*```'
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()
        # Fallback: just remove ``` lines
        if text.startswith("```"):
            lines = text.split('\n')
            # Remove first line if it's ``` or ```json
            if lines[0].strip().startswith("```"):
                lines = lines[1:]
            # Remove last line if it's ```
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            return '\n'.join(lines).strip()
        return text

    def _extract_json_object(self, text):
        """Extract the first balanced {} JSON object from text."""
        start = text.find('{')
        if start == -1:
            return None
        depth = 0
        in_string = False
        escape_next = False
        for i in range(start, len(text)):
            c = text[i]
            if escape_next:
                escape_next = False
                continue
            if c == '\\' and in_string:
                escape_next = True
                continue
            if c == '"' and not escape_next:
                in_string = not in_string
                continue
            if not in_string:
                if c == '{':
                    depth += 1
                elif c == '}':
                    depth -= 1
                    if depth == 0:
                        return text[start:i + 1]
        return None

    # ── prompt builders ───────────────────────────────────────────────────────

    def _build_long_prompt(self, topic, genes, ch):
        niche_cfg = self._load_niche(ch.get("niche", ""))
        target_min = ch.get("long_video_target_min", 8)
        target_max = ch.get("long_video_target_max", 12)
        target_wpm = genes.get("narration_pace_wpm", 155)
        target_words = int(((target_min + target_max) / 2) * target_wpm)

        hook_type   = genes.get("hook_type", "curiosity_gap")
        narrative   = genes.get("narrative_structure", "documentary_reveal")
        narr_style  = genes.get("narration_style", "authoritative_dramatic")
        payoff_pct  = genes.get("payoff_placement_pct", 0.70)
        explanation = genes.get("explanation_depth", "medium")
        citations   = genes.get("source_citation_density", "light")
        pacing      = genes.get("pacing_profile", "fast_hook_slow_reveal")

        return f"""You are a world-class YouTube scriptwriter for the channel "{ch.get('name', 'Lyra')}" in the "{niche_cfg.get('display_name', ch.get('niche', ''))}" niche.

TOPIC: {topic['topic']}
WHY NOW: {topic.get('why_now', 'Currently trending and highly relevant')}
AUDIENCE STATE: {topic.get('audience_state', 'entertainment-seeking')}
HOOK TYPE: {hook_type}
NARRATIVE STRUCTURE: {narrative}
NARRATION STYLE: {narr_style}
TARGET LENGTH: {target_min}-{target_max} minutes ({target_words} words approximately)
PAYOFF PLACEMENT: Main reveal at {int(payoff_pct * 100)}% through the video
EXPLANATION DEPTH: {explanation}
SOURCE CITATIONS: {citations}
PACING PROFILE: {pacing}
AUDIENCE IDENTITY: {niche_cfg.get('audience_archetype', 'curious truth-seekers')}

STRUCTURE:
- HOOK (first 30 seconds): Use {hook_type}. Make a clear, fulfillable promise.
- SETUP: Establish why this matters. Give context.
- ESCALATION: Build tension. Reveal supporting facts.
- REVEAL/PAYOFF (around {int(payoff_pct * 100)}% mark): Deliver the main promise.
- CLOSE: Resolve cleanly. End with CTA.

RULES:
- No filler sentences. Every sentence must serve the promise.
- No jargon without explanation.
- No robotic transitions ("In this video we will..." is forbidden).
- Write as a confident, knowledgeable narrator.

CRITICAL: Return ONLY valid JSON. No markdown fences. No explanation before or after.
{{
  "title_candidates": ["title 1", "title 2", "title 3"],
  "thumbnail_text": "MAX 4 WORDS",
  "full_narration": "complete narration text approximately {target_words} words",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8"],
  "scenes": [
    {{
      "scene_id": 1,
      "duration_estimate_sec": 25,
      "narration": "exact narration for this scene",
      "visual_description": "what to show: scene, mood, colors",
      "text_overlay": "short on-screen text or empty string",
      "intensity": "high",
      "pacing": "fast"
    }}
  ]
}}"""

    def _build_short_prompt(self, topic, genes, ch):
        niche_cfg = self._load_niche(ch.get("niche", ""))
        hook_type = genes.get("hook_type", "curiosity_gap")
        narr_style = genes.get("narration_style", "authoritative_dramatic")

        return f"""You are a YouTube Shorts scriptwriter for "{ch.get('name', 'Lyra')}" in the "{niche_cfg.get('display_name', ch.get('niche', ''))}" niche.

Create a VERTICAL SHORT (45-58 seconds):
TOPIC: {topic['topic']}
HOOK TYPE: {hook_type}
NARRATION STYLE: {narr_style}
TARGET: 130-160 words

STRUCTURE:
- Seconds 0-5: HOOK. Shocking statement or curiosity gap.
- Seconds 5-40: RAPID PAYOFF. 3-4 key revelations.
- Seconds 40-55: CLOSE. Punch line or cliffhanger.

RULES:
- First word must grab attention.
- Zero filler. Every sentence earns its place.
- Speak directly to the viewer.

CRITICAL: Return ONLY valid JSON. No markdown fences. No text before or after.
{{
  "shorts_title": "title under 60 chars",
  "full_narration": "complete 130-160 word narration",
  "scenes": [
    {{
      "scene_id": 1,
      "duration_estimate_sec": 8,
      "narration": "narration for this scene",
      "visual_description": "bold visual description",
      "text_overlay": "text on screen",
      "intensity": "high",
      "pacing": "fast"
    }}
  ]
}}"""

    # ── LLM call with fallback ────────────────────────────────────────────────

    def _call_llm(self, prompt, max_tokens=3000):
        """Call Gemini, fallback to Groq on failure."""
        try:
            result = self._call_gemini(prompt, max_tokens)
            if result:
                return result
        except Exception as e:
            log.warning(f"Gemini failed ({e}), trying Groq fallback")

        try:
            return self._call_groq(prompt, max_tokens)
        except Exception as e:
            log.error(f"Both Gemini and Groq failed: {e}")
            return None

    def _call_gemini(self, prompt, max_tokens):
        if not self.gemini_key:
            raise ValueError("GEMINI_API_KEY not set")
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"gemini-1.5-flash:generateContent?key={self.gemini_key}")
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": 0.75,
                "responseMimeType": "application/json"
            }
        }
        r = requests.post(url, json=body, timeout=90)
        if r.status_code == 429:
            log.warning("Gemini rate limited (429)")
            raise Exception("Rate limited")
        r.raise_for_status()
        data = r.json()
        candidates = data.get("candidates", [])
        if not candidates:
            log.error(f"Gemini returned no candidates: {json.dumps(data)[:300]}")
            raise Exception("No candidates in Gemini response")
        text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        if not text:
            log.error("Gemini returned empty text")
            raise Exception("Empty Gemini response")
        return text.strip()

    def _call_groq(self, prompt, max_tokens):
        if not self.groq_key:
            raise ValueError("GROQ_API_KEY not set")
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self.groq_key}",
                   "Content-Type": "application/json"}
        body = {
            "model": "llama-3.1-8b-instant",
            "messages": [
                {"role": "system", "content": "You are a JSON-only scriptwriter. Return only valid JSON with no markdown fences or extra text."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": max_tokens,
            "temperature": 0.75,
            "response_format": {"type": "json_object"}
        }
        r = requests.post(url, json=body, headers=headers, timeout=90)
        r.raise_for_status()
        text = r.json()["choices"][0]["message"]["content"].strip()
        return text

    def _save_script(self, script_id, video_type, data):
        fname = f"script_{script_id}_{video_type}.json"
        path = os.path.join(self.root, f"creation/scripts/{fname}")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def _load_niche(self, niche):
        try:
            with open(os.path.join(self.root, "data/niche_config.json")) as f:
                return json.load(f)["niches"].get(niche, {})
        except Exception:
            return {}
