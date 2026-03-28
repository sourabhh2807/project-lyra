"""
analytics_agent.py — Pulls YouTube Analytics for all recent videos.
Computes composite fitness scores. Updates genome.db.
Runs every 48 hours via GitHub Actions.
"""
import os, json, sqlite3, logging, requests, time
from datetime import datetime, timezone, timedelta

log = logging.getLogger("analytics_agent")

YT_ANALYTICS  = "https://youtubeanalytics.googleapis.com/v2/reports"
YT_VIDEOS_API = "https://www.googleapis.com/youtube/v3/videos"
YT_COMMENTS   = "https://www.googleapis.com/youtube/v3/commentThreads"

class AnalyticsAgent:
    def __init__(self, root):
        self.root   = root
        self.yt_key = os.environ.get("YOUTUBE_API_KEY", "")
        self.db     = os.path.join(root, "data/genome.db")

    def pull_and_score(self, slot):
        """Pull analytics for all recent uploads on slot, compute fitness, update DB."""
        token = os.environ.get(f"YT_OAUTH_TOKEN_{slot}", "")
        if not token:
            log.warning(f"No token for slot {slot}, skipping analytics")
            return

        # Get genomes published in last 14 days that haven't been fully evaluated
        genomes = self._get_unevaluated_genomes(slot)
        log.info(f"Slot {slot}: {len(genomes)} genomes to evaluate")

        for genome in genomes:
            vid_id = genome["video_id_youtube"]
            if not vid_id:
                continue
            try:
                metrics = self._fetch_video_metrics(vid_id, token)
                if not metrics:
                    continue

                fitness = self._compute_fitness(metrics)
                derived = self._compute_derived(metrics)

                # Update genome fitness in DB
                self._update_genome_fitness(genome["genome_id"], fitness, metrics, derived)
                log.info(f"  {vid_id}: fitness={fitness:.3f} "
                         f"(CTR={metrics.get('ctr',0):.2f}% "
                         f"AVD={metrics.get('avg_view_duration_pct',0):.1f}%)")

                time.sleep(0.5)
            except Exception as e:
                log.warning(f"  Failed to score {vid_id}: {e}")

    # ── metric fetching ───────────────────────────────────────────────────────

    def _fetch_video_metrics(self, video_id, token):
        """Fetch core metrics from YouTube Data API v3."""
        try:
            headers = {"Authorization": f"Bearer {token}"}

            # Video stats
            r = requests.get(
                YT_VIDEOS_API,
                params={"part": "statistics,contentDetails", "id": video_id,
                        "key": self.yt_key},
                headers=headers, timeout=15
            )
            if r.status_code != 200:
                log.warning(f"Video API {r.status_code} for {video_id}")
                return None

            items = r.json().get("items", [])
            if not items:
                return None

            stats    = items[0].get("statistics", {})
            content  = items[0].get("contentDetails", {})

            views    = int(stats.get("viewCount",    0))
            likes    = int(stats.get("likeCount",    0))
            comments = int(stats.get("commentCount", 0))

            # Parse duration to seconds
            duration_sec = self._iso_duration_to_sec(
                content.get("duration", "PT0S")
            )

            # Comment depth scoring (sample 10 comments)
            comment_depth = self._score_comment_depth(video_id, token)

            # Note: full CTR and AVD require YouTube Analytics API with OAuth
            # Using estimates from public stats as fallback
            like_ratio = likes / max(views, 1)

            return {
                "views_48h":              views,
                "likes":                  likes,
                "like_ratio":             like_ratio,
                "comment_count":          comments,
                "comment_depth_score":    comment_depth,
                "duration_sec":           duration_sec,
                "ctr":                    0.0,    # filled by Analytics API if available
                "avg_view_duration_pct":  0.0,    # filled by Analytics API if available
                "retention_stability":    0.5,    # default until Analytics available
            }

        except Exception as e:
            log.warning(f"Metrics fetch error: {e}")
            return None

    def _score_comment_depth(self, video_id, token):
        """Score 0.0–1.0: how deep/engaged are the comments."""
        try:
            r = requests.get(
                YT_COMMENTS,
                params={"part": "snippet", "videoId": video_id,
                        "maxResults": 10, "order": "relevance",
                        "key": self.yt_key},
                timeout=10
            )
            if r.status_code != 200:
                return 0.3  # default

            items = r.json().get("items", [])
            if not items:
                return 0.1

            word_counts = []
            for item in items:
                text = item["snippet"]["topLevelComment"]["snippet"]["textDisplay"]
                # Filter out pure emoji / very short comments
                words = [w for w in text.split() if len(w) > 1]
                word_counts.append(len(words))

            if not word_counts:
                return 0.1

            avg_words = sum(word_counts) / len(word_counts)
            # 3 words = 0.1, 15 words = 0.6, 30+ words = 1.0
            score = min(1.0, avg_words / 30.0)
            return round(score, 3)
        except Exception:
            return 0.3

    # ── fitness computation ───────────────────────────────────────────────────

    def _compute_fitness(self, metrics):
        """
        Composite fitness formula:
        0.28*satisfaction + 0.22*avd + 0.15*retention_stability
        + 0.12*ctr_quality + 0.10*comment_depth + 0.08*return_lift + 0.05*originality
        """
        views     = metrics.get("views_48h", 0)
        like_r    = metrics.get("like_ratio", 0)
        comments  = metrics.get("comment_count", 0)
        depth     = metrics.get("comment_depth_score", 0.3)
        ctr       = metrics.get("ctr", 0.0)
        avd_pct   = metrics.get("avg_view_duration_pct", 0.0)
        ret_stab  = metrics.get("retention_stability", 0.5)

        # Satisfaction: weighted like ratio + save/share signal (using saves proxy)
        satisfaction = min(1.0, like_r * 25.0 + (comments / max(views, 1)) * 10.0)

        # AVD score: normalize 0-100 → 0-1
        avd_score = min(1.0, avd_pct / 60.0)   # 60% retention = 1.0

        # CTR quality: normalize 0-20% → 0-1, with penalty for <1%
        ctr_quality = min(1.0, ctr / 8.0) if ctr >= 1.0 else ctr / 8.0 * 0.5

        # View velocity (raw views in 48h, normalized by channel baseline — use 1000 as start)
        view_norm = min(1.0, views / 5000.0)

        # Simple weighted sum
        fitness = (
            0.28 * satisfaction +
            0.22 * avd_score +
            0.15 * ret_stab +
            0.12 * ctr_quality +
            0.10 * depth +
            0.08 * view_norm +
            0.05 * 0.5          # originality default 0.5
        )
        return round(min(1.0, max(0.0, fitness)), 4)

    def _compute_derived(self, metrics):
        views = metrics.get("views_48h", 0)
        dur   = metrics.get("duration_sec", 1)
        avd   = metrics.get("avg_view_duration_pct", 0)

        hook_strength    = min(1.0, avd / 40.0)   # proxy for 30-sec retention
        payoff_score     = min(1.0, avd / 55.0)   # proxy for end-of-video retention
        pacing_overload  = 0.3                     # placeholder
        return {
            "hook_strength_score":      round(hook_strength, 3),
            "payoff_fulfillment_score": round(payoff_score, 3),
            "pacing_overload_score":    pacing_overload,
        }

    # ── DB helpers ────────────────────────────────────────────────────────────

    def _get_unevaluated_genomes(self, slot):
        conn = sqlite3.connect(self.db)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("""
            SELECT genome_id, video_id_youtube, genes, niche
            FROM genomes
            WHERE channel_slot=? AND status='published'
              AND (fitness_score=0.0 OR evaluated_at='')
              AND video_id_youtube != ''
        """, (slot,))
        rows = [dict(r) for r in c.fetchall()]
        conn.close()
        return rows

    def _update_genome_fitness(self, genome_id, fitness, metrics, derived):
        conn = sqlite3.connect(self.db)
        c = conn.cursor()
        c.execute("""
            UPDATE genomes
            SET fitness_score=?, status='evaluated', evaluated_at=?
            WHERE genome_id=?
        """, (fitness, datetime.now(timezone.utc).isoformat(), genome_id))

        c.execute("""
            INSERT OR REPLACE INTO fitness_history
            (genome_id, channel_slot, video_id_youtube, video_type,
             views_48h, ctr_pct, avg_view_duration_pct,
             like_ratio, comment_count, comment_depth_score,
             composite_fitness, hook_strength_score,
             payoff_fulfillment_score, evaluated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            genome_id, 0, metrics.get("video_id",""), "long",
            metrics["views_48h"], metrics["ctr"],
            metrics["avg_view_duration_pct"], metrics["like_ratio"],
            metrics["comment_count"], metrics["comment_depth_score"],
            fitness,
            derived["hook_strength_score"],
            derived["payoff_fulfillment_score"],
            datetime.now(timezone.utc).isoformat()
        ))
        conn.commit()
        conn.close()

    @staticmethod
    def _iso_duration_to_sec(duration):
        """Convert ISO 8601 duration (PT10M30S) to seconds."""
        import re
        m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration)
        if not m:
            return 0
        h = int(m.group(1) or 0)
        mn = int(m.group(2) or 0)
        s = int(m.group(3) or 0)
        return h * 3600 + mn * 60 + s
