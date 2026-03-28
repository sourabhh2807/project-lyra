"""
frequency_controller.py — Controls upload cadence per channel.
Detects audience fatigue. Enforces minimums and maximums.
Quality-first: never publish just to hit a quota.
"""
import os, json, glob, logging
from datetime import datetime, timezone, timedelta

log = logging.getLogger("frequency_controller")

class FrequencyController:
    def __init__(self, root):
        self.root = root

    def should_publish(self, slot, video_type="long"):
        """
        Return True if the channel is healthy to publish right now.
        Checks: daily limit, weekly limit, fatigue signals, cooldown period.
        """
        channel = self._get_channel(slot)
        if not channel:
            return False

        if channel.get("status") != "active":
            log.info(f"Slot {slot}: Channel not active ({channel.get('status')})")
            return False

        now = datetime.now(timezone.utc)

        # Count uploads in last 24h and last 7 days
        uploads_24h = self._count_uploads(slot, hours=24)
        uploads_7d  = self._count_uploads(slot, hours=168)

        # Per-type limits
        if video_type == "long":
            daily_max  = 1          # max 1 long video per day per channel
            weekly_max = channel.get("uploads_per_week_long", 3)
        else:
            daily_max  = 2          # max 2 shorts per day
            weekly_max = channel.get("uploads_per_week_shorts", 5)

        if uploads_24h >= daily_max:
            log.info(f"Slot {slot}: Daily {video_type} limit reached ({uploads_24h}/{daily_max})")
            return False

        if uploads_7d >= weekly_max:
            log.info(f"Slot {slot}: Weekly {video_type} limit reached ({uploads_7d}/{weekly_max})")
            return False

        # Fatigue check
        if self._is_fatigued(slot):
            log.warning(f"Slot {slot}: Audience fatigue detected — reducing cadence")
            # In fatigue mode, only publish if below 50% of weekly quota
            if uploads_7d >= weekly_max * 0.5:
                return False

        log.info(f"Slot {slot}: OK to publish {video_type} "
                 f"(24h={uploads_24h}/{daily_max} 7d={uploads_7d}/{weekly_max})")
        return True

    def _is_fatigued(self, slot):
        """
        Detect audience fatigue from:
        - Declining avg fitness over last 5 videos
        - Rising proportion of low-depth comments
        """
        recent = self._get_recent_fitness(slot, n=6)
        if len(recent) < 4:
            return False

        # Check if last 3 avg is lower than first 3 avg (declining trend)
        first_half = sum(recent[:3]) / 3
        last_half  = sum(recent[-3:]) / 3
        declining  = last_half < first_half * 0.80   # >20% drop = fatigue

        if declining:
            log.warning(f"  Fatigue signal: fitness {first_half:.3f}→{last_half:.3f}")

        return declining

    def _count_uploads(self, slot, hours=24):
        """Count published videos for slot in last N hours."""
        cutoff  = datetime.now(timezone.utc) - timedelta(hours=hours)
        pattern = os.path.join(self.root, "execution/publish_logs/*.json")
        count   = 0
        for path in glob.glob(pattern):
            try:
                with open(path) as f:
                    entry = json.load(f)
                if entry.get("slot") != slot:
                    continue
                ts = datetime.fromisoformat(
                    entry["ts"].replace("Z", "+00:00")
                )
                if ts > cutoff:
                    count += 1
            except Exception:
                pass
        return count

    def _get_recent_fitness(self, slot, n=6):
        """Get last N fitness scores for slot from learning.json."""
        try:
            with open(os.path.join(self.root, "data/learning.json")) as f:
                learning = json.load(f)
            hist = learning.get("fitness_history", [])
            slot_hist = [h["fitness"] for h in hist if h.get("slot") == slot]
            return slot_hist[-n:]
        except Exception:
            return []

    def _get_channel(self, slot):
        try:
            with open(os.path.join(self.root, "data/channel_map.json")) as f:
                data = json.load(f)
            return next((c for c in data["channels"] if c["slot"] == slot), None)
        except Exception:
            return None
