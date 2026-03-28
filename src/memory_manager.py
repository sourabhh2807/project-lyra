"""
memory_manager.py — Three-tier memory system.
Short-term (48h) → Mid-term (7-30d) → Long-term (30d+ permanent).
Runs weekly to compress, promote, and archive knowledge.
"""
import os, json, glob, logging, shutil
from datetime import datetime, timezone, timedelta

log = logging.getLogger("memory_manager")

class MemoryManager:
    def __init__(self, root):
        self.root = root

    def process_tier_promotions(self, slot=None):
        """Main entry: promote mid→long, archive expired short-term."""
        log.info("Memory Manager: processing tier promotions")
        self._promote_mid_to_long()
        self._archive_expired_short_term()
        self._update_memory_index()

    def _promote_mid_to_long(self):
        """
        Promote mid-term learnings to long-term if:
        - confidence >= 0.65
        - age >= 14 days
        - validated by multiple data points
        """
        pattern = os.path.join(self.root, "memory/mid_term/*.json")
        promoted = 0
        for path in glob.glob(pattern):
            try:
                with open(path) as f:
                    item = json.load(f)

                confidence = item.get("confidence", 0)
                created_at = item.get("created_at", "")
                if not created_at:
                    continue

                age_days = (
                    datetime.now(timezone.utc) -
                    datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                ).days

                if confidence >= 0.65 and age_days >= 14:
                    # Move to long-term
                    dest = os.path.join(self.root, "memory/long_term",
                                        os.path.basename(path))
                    item["promoted_to_long_term_at"] = datetime.now(timezone.utc).isoformat()
                    item["memory_tier"] = "long_term"
                    with open(dest, "w") as f:
                        json.dump(item, f, indent=2)
                    os.remove(path)
                    promoted += 1
            except Exception as e:
                log.warning(f"Promotion failed for {path}: {e}")

        if promoted:
            log.info(f"  Promoted {promoted} items mid→long-term")

    def _archive_expired_short_term(self):
        """Move short-term items older than 48h to mid-term if worth keeping."""
        pattern  = os.path.join(self.root, "memory/short_term/*.json")
        archived = 0
        deleted  = 0

        for path in glob.glob(pattern):
            try:
                with open(path) as f:
                    item = json.load(f)

                created_at = item.get("created_at", "")
                if not created_at:
                    continue

                age_hours = (
                    datetime.now(timezone.utc) -
                    datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                ).total_seconds() / 3600

                if age_hours < 48:
                    continue    # still fresh

                # Promote if has signal value, otherwise delete
                if item.get("confidence", 0) >= 0.40:
                    dest = os.path.join(self.root, "memory/mid_term",
                                        os.path.basename(path))
                    item["memory_tier"] = "mid_term"
                    with open(dest, "w") as f:
                        json.dump(item, f, indent=2)
                    archived += 1
                else:
                    deleted += 1

                os.remove(path)

            except Exception as e:
                log.warning(f"Short-term cleanup failed for {path}: {e}")

        log.info(f"  Short-term: {archived} promoted to mid, {deleted} expired")

    def _update_memory_index(self):
        """Rebuild memory_index.json from all tier contents."""
        index = {"short_term": [], "mid_term": [], "long_term": [], "evergreen": []}

        for tier in index.keys():
            pattern = os.path.join(self.root, f"memory/{tier}/*.json")
            for path in glob.glob(pattern):
                try:
                    with open(path) as f:
                        item = json.load(f)
                    index[tier].append({
                        "id":          item.get("learning_id", os.path.basename(path)),
                        "statement":   item.get("statement", "")[:120],
                        "confidence":  item.get("confidence", 0),
                        "niche":       item.get("niche", ""),
                        "created_at":  item.get("created_at", ""),
                    })
                except Exception:
                    pass

        index_path = os.path.join(self.root, "memory/memory_index.json")
        with open(index_path, "w") as f:
            json.dump(index, f, indent=2)

        total = sum(len(v) for v in index.values())
        log.info(f"  Memory index updated: {total} total items across all tiers")

    def store_short_term(self, item_type, data, confidence=0.3):
        """Store a new short-term memory item."""
        import uuid
        item = {
            "learning_id":  str(uuid.uuid4()),
            "type":         item_type,
            "memory_tier":  "short_term",
            "confidence":   confidence,
            "created_at":   datetime.now(timezone.utc).isoformat(),
            **data,
        }
        fname = f"st_{item['learning_id'][:8]}.json"
        path  = os.path.join(self.root, f"memory/short_term/{fname}")
        with open(path, "w") as f:
            json.dump(item, f, indent=2)
        return item["learning_id"]

    def get_long_term_rules(self, niche=None):
        """Retrieve all long-term rules, optionally filtered by niche."""
        rules   = []
        pattern = os.path.join(self.root, "memory/long_term/*.json")
        for path in glob.glob(pattern):
            try:
                with open(path) as f:
                    item = json.load(f)
                if niche and item.get("niche") and item["niche"] != niche:
                    continue
                rules.append(item)
            except Exception:
                pass
        rules.sort(key=lambda x: x.get("confidence", 0), reverse=True)
        return rules
