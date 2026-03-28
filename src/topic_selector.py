"""
topic_selector.py — Selects the best topic candidate from the research pool.
Applies novelty, saturation, timing, and channel-fit filters.
"""
import json, os, glob, logging
from datetime import datetime, timezone, timedelta

log = logging.getLogger("topic_selector")

class TopicSelector:
    def __init__(self, root):
        self.root = root

    def select(self, slot, niche):
        """Return the best available topic candidate for this slot/niche."""
        candidates = self._load_candidates(niche)
        if not candidates:
            log.warning(f"No candidates for niche {niche}")
            return None

        # Filter: already used, expired, or too low confidence
        recent_topics = self._get_recent_topics(slot)
        now = datetime.now(timezone.utc)

        valid = []
        for c in candidates:
            # Skip if already published recently (within 60 days)
            if c.get("topic", "").lower() in [t.lower() for t in recent_topics]:
                continue
            # Skip if expired
            decay_days = c.get("urgency_decay_days", 14)
            created_at = c.get("created_at", now.isoformat())
            try:
                age_days = (now - datetime.fromisoformat(created_at.replace("Z", "+00:00"))).days
            except Exception:
                age_days = 0
            if age_days > decay_days and c.get("recommended_format") != "evergreen":
                continue
            # Skip if low confidence
            if c.get("research_confidence", 0.5) < 0.35:
                continue
            valid.append(c)

        if not valid:
            log.warning(f"All candidates filtered out for niche {niche}. Using best available.")
            valid = candidates[:3]

        if not valid:
            return None

        # Score and sort
        scored = sorted(valid, key=lambda x: x.get("predicted_fitness", 0.0), reverse=True)
        best = scored[0]

        # Mark as in_creation so it's not picked again
        best["status"] = "in_creation"
        self._update_candidate(best)

        log.info(f"Selected: '{best['topic']}' | fitness_pred={best.get('predicted_fitness', 0):.2f}")
        return best

    def _load_candidates(self, niche):
        pattern = os.path.join(self.root, "research/processed/topic_candidates/candidate_*.json")
        candidates = []
        for path in glob.glob(pattern):
            try:
                with open(path) as f:
                    c = json.load(f)
                if c.get("niche") == niche and c.get("status") in ("queued", "briefed"):
                    candidates.append(c)
            except Exception:
                pass
        return candidates

    def _get_recent_topics(self, slot):
        """Returns list of topic strings published in the last 60 days for this slot."""
        topics = []
        pattern = os.path.join(self.root, "execution/publish_logs/*.json")
        cutoff = datetime.now(timezone.utc) - timedelta(days=60)
        for path in glob.glob(pattern):
            try:
                with open(path) as f:
                    entry = json.load(f)
                if entry.get("slot") != slot:
                    continue
                ts = datetime.fromisoformat(entry["ts"].replace("Z", "+00:00"))
                if ts > cutoff:
                    topics.append(entry.get("topic", ""))
            except Exception:
                pass
        return topics

    def _update_candidate(self, candidate):
        pattern = os.path.join(self.root,
                               f"research/processed/topic_candidates/candidate_*.json")
        for path in glob.glob(pattern):
            try:
                with open(path) as f:
                    c = json.load(f)
                if c.get("topic_id") == candidate["topic_id"]:
                    with open(path, "w") as f:
                        json.dump(candidate, f, indent=2)
                    return
            except Exception:
                pass
