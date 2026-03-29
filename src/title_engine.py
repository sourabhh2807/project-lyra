"""
title_engine.py — Generates titles, descriptions, and tags using Gemini.
Scores against title patterns. Enforces honesty gate.
"""
import os, json, requests, logging, re
from datetime import datetime

log = logging.getLogger("title_engine")

class TitleEngine:
    def __init__(self, root):
        self.root   = root
        self.gemini = os.environ.get("GEMINI_API_KEY", "")
        self.groq   = os.environ.get("GROQ_API_KEY", "")
        with open(os.path.join(root, "data/title_patterns.json")) as f:
            self.patterns = json.load(f)["patterns"]

    # ── public ───────────────────────────────────────────────────────────────

    def generate(self, topic, genome, channel_config, niche_config):
        """Generate full metadata for long video. Returns dict."""
        niche     = genome["niche"]
        genes     = genome["genes"]
        niche_cfg = niche_config.get("niches", {}).get(niche, {})
        archetype = genes.get("title_archetype", "the_truth_about")

        prompt = self._build_title_prompt(topic, genes, channel_config, niche_cfg, archetype)
        try:
            raw  = self._call_llm(prompt)
            data = json.loads(raw)
        except Exception as e:
            log.error(f"Title generation failed: {e}")
            data = self._fallback_metadata(topic, niche_cfg)

        # Select best title: score candidates
        candidates = data.get("title_candidates", [data.get("title", topic["topic"])])
        best_title = self._score_and_select(candidates, topic, genes)

        return {
            "title":       best_title,
            "description": data.get("description", self._fallback_desc(topic)),
            "tags":        data.get("tags", topic.get("tags_suggested", [])),
            "chapters":    data.get("chapters", []),
        }

    def generate_shorts(self, topic, genome, channel_config):
        """Generate metadata specifically for a YouTube Short."""
        niche = genome["niche"]
        prompt = f"""Write YouTube Shorts metadata for:
Topic: {topic.get('topic', '')}
Niche: {niche}

Return ONLY valid JSON:
{{
  "title": "Shorts title under 60 chars, starts with hook word (NOT 'In' or 'Today')",
  "description": "2-3 sentence description with 3-4 hashtags at end",
  "tags": ["tag1","tag2","tag3","tag4","tag5"]
}}"""
        try:
            raw  = self._call_llm(prompt, max_tokens=300)
            data = json.loads(raw)
        except Exception:
            data = {
                "title":       f"{topic.get('topic', 'Watch This')} #shorts",
                "description": f"{topic.get('topic', '')} #shorts #{niche.replace('_', '')}",
                "tags":        [niche, "shorts", "viral"]
            }
        return data

    # ── scoring ───────────────────────────────────────────────────────────────

    def _score_and_select(self, candidates, topic, genes):
        if not candidates:
            return topic.get("topic", "Untitled")

        best, best_score = candidates[0], -1
        for title in candidates:
            score = self._score_title(title, topic, genes)
            if score > best_score:
                best, best_score = title, score

        log.info(f"Best title: '{best}' (score={best_score:.2f})")
        return best

    def _score_title(self, title, topic, genes):
        score = 0.0
        t = title.lower()

        # Specificity: has numbers or specific nouns
        if re.search(r'\d', title): score += 0.15
        # Curiosity gap: unanswered implication
        if any(w in t for w in ["actually", "real", "truth", "hidden", "secret",
                                  "nobody", "they", "dark", "inside"]):
            score += 0.20
        # Length sweet spot: 45-65 chars
        if 45 <= len(title) <= 65: score += 0.15
        # Starts with strong word (not weak opener)
        weak_openers = ["in ", "today ", "this ", "here ", "so "]
        if not any(title.lower().startswith(w) for w in weak_openers): score += 0.10
        # Identity relevance from topic
        identity = topic.get("audience_fears_triggered", [])
        if any(fear.lower()[:8] in t for fear in identity): score += 0.10
        # Matches title archetype gene
        archetype_id = genes.get("title_archetype", "")
        pattern = next((p for p in self.patterns if p["id"] == archetype_id), None)
        if pattern:
            pattern_words = pattern["template"].lower().split()
            if any(w.replace("{", "").replace("}", "") in t
                   for w in pattern_words if len(w) > 4):
                score += 0.15
        # Not clickbait alone: avoid "YOU WON'T BELIEVE" without substance
        if "you won't believe" in t and not any(
                w in t for w in ["how", "why", "when", "what", "who"]):
            score -= 0.20

        return score

    # ── prompt builders ───────────────────────────────────────────────────────

    def _build_title_prompt(self, topic, genes, ch, niche_cfg, archetype):
        pattern = next((p for p in self.patterns if p["id"] == archetype),
                       self.patterns[0])
        kws = niche_cfg.get("trending_seed_keywords", [])[:5]
        return f"""You are a YouTube SEO expert for the channel "{ch['name']}".

Topic: {topic['topic']}
Why now: {topic.get('why_now', '')}
Title pattern to use: "{pattern['template']}" (example: "{pattern['example']}")
Target emotion: {pattern['emotion']}
SEO keywords to weave in naturally: {', '.join(kws)}
Audience identity: {niche_cfg.get('identity_archetype', 'curious viewers')}

Create compelling, honest YouTube metadata.

Return ONLY valid JSON:
{{
  "title_candidates": [
    "best title using pattern",
    "alternative title variation",
    "third option slightly different angle"
  ],
  "description": "Full YouTube description, 200-300 words. First 2 lines must hook. Include timestamps placeholder [CHAPTERS]. End with 5-6 relevant hashtags.",
  "tags": ["tag1","tag2","tag3","tag4","tag5","tag6","tag7","tag8","tag9","tag10"],
  "chapters": [
    {{"time": "0:00", "title": "Introduction"}},
    {{"time": "1:30", "title": "Chapter title"}},
    {{"time": "5:00", "title": "Main reveal"}}
  ]
}}

RULES: Titles must be honest — promise only what the video delivers.
No ALL CAPS entire title. Max 70 characters per title candidate."""

    # ── fallbacks ─────────────────────────────────────────────────────────────

    def _fallback_metadata(self, topic, niche_cfg):
        t = topic.get("topic", "Untitled")
        return {
            "title_candidates": [f"The Truth About {t}", f"What Nobody Tells You About {t}"],
            "description":      f"In this video we explore: {t}\n\n#{niche_cfg.get('display_name','').replace(' ','')}",
            "tags":             niche_cfg.get("trending_seed_keywords", [])[:8],
            "chapters":         [{"time": "0:00", "title": "Intro"}],
        }

    def _fallback_desc(self, topic):
        return f"{topic.get('topic', '')} — {topic.get('why_now', '')}\n\nWatch to the end for the full story."

    # ── LLM ──────────────────────────────────────────────────────────────────

    def _call_llm(self, prompt, max_tokens=700):
        try:
            return self._call_gemini(prompt, max_tokens)
        except Exception as e:
            log.warning(f"Gemini failed ({e}), using Groq")
            return self._call_groq(prompt, max_tokens)

    def _call_gemini(self, prompt, max_tokens):
        if not self.gemini: raise ValueError("No GEMINI_API_KEY")
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"gemini-2.5-flash:generateContent?key={self.gemini}")
        body = {"contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.7,
                                     "responseMimeType": "application/json"}}
        r = requests.post(url, json=body, timeout=30)
        r.raise_for_status()
        text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        return self._clean(text)

    def _call_groq(self, prompt, max_tokens):
        if not self.groq: raise ValueError("No GROQ_API_KEY")
        url  = "https://api.groq.com/openai/v1/chat/completions"
        hdrs = {"Authorization": f"Bearer {self.groq}", "Content-Type": "application/json"}
        body = {"model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens, "temperature": 0.7}
        r = requests.post(url, json=body, headers=hdrs, timeout=30)
        r.raise_for_status()
        text = r.json()["choices"][0]["message"]["content"].strip()
        return self._clean(text)

    def _clean(self, text):
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"): text = text[4:]
        return text.strip()
