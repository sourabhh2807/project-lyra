"""
research_agent.py — 24/7 trend sensing, competitor intelligence, topic candidate generation.
Runs hourly via GitHub Actions. Writes structured topic objects to research/processed/.
"""
import json, os, sys, logging, uuid, time, requests
from datetime import datetime, timezone, timedelta

log = logging.getLogger("research_agent")

class ResearchAgent:
    def __init__(self, root):
        self.root = root
        self.gemini_key = os.environ.get("GEMINI_API_KEY", "")
        self.yt_key     = os.environ.get("YOUTUBE_API_KEY", "")

    # ── public entry point ────────────────────────────────────────────────────

    def run(self, slot, niche):
        log.info(f"Research: slot={slot} niche={niche}")
        niche_cfg = self._load_niche(niche)
        if not niche_cfg:
            log.warning(f"No niche config for {niche}")
            return

        # A. Gather raw signals
        trends   = self._fetch_trends(niche_cfg)
        yt_trend = self._fetch_yt_trending(niche_cfg)
        audience = self._load_or_build_audience_map(niche)

        # B. Merge and deduplicate signals
        raw_signals = list({s["query"]: s for s in trends + yt_trend}.values())
        log.info(f"  Raw signals collected: {len(raw_signals)}")

        # C. Filter and score each signal → topic candidates
        candidates = []
        for signal in raw_signals[:20]:  # Cap at 20 to save API quota
            cand = self._build_topic_candidate(signal, niche, niche_cfg, audience)
            if cand and cand["novelty_score"] > 0.3 and cand["saturation_score"] < 0.75:
                candidates.append(cand)

        # D. Save candidates
        for cand in candidates[:10]:  # Top 10
            self._save_candidate(cand)

        log.info(f"  Candidates saved: {len(candidates[:10])}")

    # ── trend fetching ────────────────────────────────────────────────────────

    def _fetch_trends(self, niche_cfg):
        """Fetch Google Trends rising queries using pytrends."""
        try:
            from pytrends.request import TrendReq
            pt = TrendReq(hl="en-US", tz=0, timeout=(10, 25))
            keywords = niche_cfg.get("trending_seed_keywords", [])[:4]
            if not keywords:
                return []
            pt.build_payload(keywords, timeframe="now 7-d", geo="")
            related = pt.related_queries()
            signals = []
            for kw in keywords:
                if kw in related and related[kw]["rising"] is not None:
                    for _, row in related[kw]["rising"].head(5).iterrows():
                        signals.append({
                            "query": row["query"],
                            "source": "google_trends",
                            "value": row["value"],
                            "keyword_parent": kw
                        })
            return signals
        except Exception as e:
            log.warning(f"Google Trends failed: {e}")
            # Return seed keywords as fallback signals
            return [{"query": kw, "source": "seed", "value": 50, "keyword_parent": kw}
                    for kw in niche_cfg.get("trending_seed_keywords", [])[:5]]

    def _fetch_yt_trending(self, niche_cfg):
        """Search YouTube for trending content in niche."""
        if not self.yt_key:
            return []
        signals = []
        try:
            for kw in niche_cfg.get("trending_seed_keywords", [])[:3]:
                url = "https://www.googleapis.com/youtube/v3/search"
                params = {
                    "part": "snippet",
                    "q": kw,
                    "type": "video",
                    "order": "viewCount",
                    "publishedAfter": (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "maxResults": 5,
                    "key": self.yt_key
                }
                r = requests.get(url, params=params, timeout=10)
                if r.status_code == 200:
                    for item in r.json().get("items", []):
                        title = item["snippet"]["title"]
                        signals.append({
                            "query": title,
                            "source": "youtube_trending",
                            "value": 70,
                            "keyword_parent": kw
                        })
                time.sleep(0.5)  # Rate limit protection
        except Exception as e:
            log.warning(f"YouTube trending fetch failed: {e}")
        return signals

    # ── topic candidate builder ───────────────────────────────────────────────

    def _build_topic_candidate(self, signal, niche, niche_cfg, audience):
        """Use Gemini to evaluate a signal and build a structured topic candidate."""
        prompt = f"""You are a content strategist for a YouTube channel in the "{niche_cfg.get('display_name', niche)}" niche.

Evaluate this topic signal and determine if it makes a good video topic:
Signal: "{signal['query']}"

Channel description: {niche_cfg.get('description', '')}
Target audience: {niche_cfg.get('target_audience', '')}

Return ONLY valid JSON, no markdown, no explanation:
{{
  "topic": "refined topic title for the video",
  "why_now": "1-2 sentences on why this is timely",
  "audience_state": "one of: unaware | problem-aware | solution-aware | comparison | emotionally-charged | entertainment-seeking",
  "emotional_dimension_primary": "one of: attention | curiosity | comprehension | tension | reward | identity",
  "content_angles": ["angle 1", "angle 2", "angle 3"],
  "audience_fears_triggered": ["fear 1", "fear 2"],
  "audience_goals_served": ["goal 1", "goal 2"],
  "open_questions": ["question viewers have", "another unanswered question"],
  "recommended_format": "one of: long | short | series | evergreen",
  "predicted_half_life_days": 14,
  "novelty_score": 0.7,
  "saturation_score": 0.3,
  "authority_fit": 0.8,
  "research_confidence": 0.7,
  "trigger_type_recommended": "one of: curiosity_gap | shock | identity | practical | taboo | contrarian"
}}"""

        try:
            response = self._call_gemini(prompt, max_tokens=600)
            data = json.loads(response)
            data["topic_id"] = str(uuid.uuid4())
            data["niche"] = niche
            data["source_signal"] = signal["query"]
            data["status"] = "queued"
            data["created_at"] = datetime.now(timezone.utc).isoformat()
            data["evidence_sources"] = [signal["source"]]
            data["urgency_decay_days"] = data.get("predicted_half_life_days", 14)
            data["predicted_fitness"] = (
                data.get("novelty_score", 0.5) * 0.4 +
                (1 - data.get("saturation_score", 0.5)) * 0.3 +
                data.get("authority_fit", 0.5) * 0.3
            )
            return data
        except Exception as e:
            log.warning(f"Candidate build failed for '{signal['query']}': {e}")
            # Build a minimal candidate without LLM on failure
            return {
                "topic_id": str(uuid.uuid4()),
                "topic": signal["query"],
                "niche": niche,
                "why_now": "Trending signal detected",
                "audience_state": "entertainment-seeking",
                "novelty_score": 0.5,
                "saturation_score": 0.5,
                "authority_fit": 0.6,
                "research_confidence": 0.4,
                "content_angles": [],
                "audience_fears_triggered": [],
                "audience_goals_served": [],
                "open_questions": [],
                "recommended_format": "long",
                "predicted_half_life_days": 14,
                "urgency_decay_days": 14,
                "predicted_fitness": 0.4,
                "trigger_type_recommended": "curiosity_gap",
                "emotional_dimension_primary": "curiosity",
                "evidence_sources": [signal["source"]],
                "source_signal": signal["query"],
                "status": "queued",
                "created_at": datetime.now(timezone.utc).isoformat()
            }

    # ── audience map ──────────────────────────────────────────────────────────

    def _load_or_build_audience_map(self, niche):
        path = os.path.join(self.root, f"research/processed/audience_maps/{niche}.json")
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
        # Build basic map from niche config
        niche_cfg = self._load_niche(niche)
        audience = {
            "niche": niche,
            "fears": [],
            "goals": [],
            "frustrations": [],
            "objections": [],
            "language_patterns": [],
            "identity_signals": [],
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
        with open(path, "w") as f:
            json.dump(audience, f, indent=2)
        return audience

    # ── persistence ───────────────────────────────────────────────────────────

    def _save_candidate(self, candidate):
        fname = f"candidate_{candidate['topic_id'][:8]}.json"
        path = os.path.join(self.root, f"research/processed/topic_candidates/{fname}")
        with open(path, "w") as f:
            json.dump(candidate, f, indent=2)

    def _load_niche(self, niche):
        cfg_path = os.path.join(self.root, "data/niche_config.json")
        with open(cfg_path) as f:
            cfg = json.load(f)
        return cfg["niches"].get(niche)

    # ── Gemini API call ───────────────────────────────────────────────────────

    def _call_gemini(self, prompt, max_tokens=1000):
        if not self.gemini_key:
            raise ValueError("GEMINI_API_KEY not set")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.gemini_key}"
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.7}
        }
        r = requests.post(url, json=body, timeout=30)
        r.raise_for_status()
        text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        # Strip markdown fences if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return text.strip()
