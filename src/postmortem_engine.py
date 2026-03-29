"""
postmortem_engine.py — Automatically generates structured postmortems for
videos with fitness < 0.25. Extracts learnings and stores to reflection/.
"""
import os, json, sqlite3, logging, uuid, requests
from datetime import datetime, timezone

log = logging.getLogger("postmortem_engine")

FITNESS_THRESHOLD = 0.25   # Below this → automatic postmortem

class PostmortemEngine:
    def __init__(self, root):
        self.root       = root
        self.db         = os.path.join(root, "data/genome.db")
        self.gemini_key = os.environ.get("GEMINI_API_KEY", "")

    def run_for_slot(self, slot):
        """Generate postmortems for all weak performers on this slot."""
        weak = self._get_weak_genomes(slot)
        log.info(f"Slot {slot}: {len(weak)} weak performers for postmortem")

        for genome in weak:
            try:
                pm = self._generate_postmortem(genome)
                self._save_postmortem(pm)
                self._extract_learning(pm, genome)
                # Mark genome as post-mortemed so we don't repeat
                self._mark_postmortemed(genome["genome_id"])
                log.info(f"  Postmortem: {genome['genome_id'][:8]} fitness={genome['fitness_score']:.3f}")
            except Exception as e:
                log.warning(f"  Postmortem failed for {genome['genome_id'][:8]}: {e}")

    def _generate_postmortem(self, genome):
        genes        = json.loads(genome["genes"])
        fitness      = genome["fitness_score"]
        fitness_hist = json.loads(genome.get("fitness_history_json", "{}"))

        # Build prompt for LLM analysis
        prompt = f"""You are a senior YouTube content strategist analyzing why a video underperformed.

VIDEO GENOME:
- Niche: {genome['niche']}
- Hook type: {genes.get('hook_type', 'unknown')}
- Narrative structure: {genes.get('narrative_structure', 'unknown')}
- Narration style: {genes.get('narration_style', 'unknown')}
- Pacing profile: {genes.get('pacing_profile', 'unknown')}
- Title archetype: {genes.get('title_archetype', 'unknown')}
- Explanation depth: {genes.get('explanation_depth', 'unknown')}

PERFORMANCE:
- Composite fitness: {fitness:.3f} (threshold: {FITNESS_THRESHOLD})
- Views 48h: {fitness_hist.get('views_48h', 'unknown')}
- Avg view duration: {fitness_hist.get('avg_view_duration_pct', 'unknown')}%
- Like ratio: {fitness_hist.get('like_ratio', 'unknown')}
- Comment depth: {fitness_hist.get('comment_depth_score', 'unknown')}

Analyze the likely failure causes. Be specific about which genes likely contributed.

Return ONLY valid JSON (no markdown):
{{
  "likely_failure_reasons": ["reason 1", "reason 2", "reason 3"],
  "where_drop_happened": "hook | setup | mid_video | payoff | all",
  "wrong_assumptions": ["assumption 1", "assumption 2"],
  "gene_diagnoses": {{
    "hook_type": "assessment of whether this hook type was right for this content",
    "narrative_structure": "was this the right structure",
    "pacing_profile": "was pacing appropriate"
  }},
  "what_to_test_next": ["test hypothesis 1", "test hypothesis 2"],
  "recommendation": "archive | remix | retry_with_changes",
  "key_learning": "one sentence: the most important insight from this failure"
}}"""

        try:
            result = self._call_gemini(prompt, 600)
            data   = json.loads(result)
        except Exception:
            data = {
                "likely_failure_reasons": ["Low engagement — likely hook or narrative mismatch"],
                "where_drop_happened":    "hook",
                "wrong_assumptions":      ["Audience state prediction may have been off"],
                "gene_diagnoses":         {},
                "what_to_test_next":      ["Try different hook type", "Try shorter video"],
                "recommendation":         "retry_with_changes",
                "key_learning":           f"Hook type '{genes.get('hook_type')}' underperformed in {genome['niche']}",
            }

        return {
            "postmortem_id":    str(uuid.uuid4()),
            "genome_id":        genome["genome_id"],
            "niche":            genome["niche"],
            "fitness_score":    fitness,
            "genes_snapshot":   genes,
            "created_at":       datetime.now(timezone.utc).isoformat(),
            **data,
        }

    def _extract_learning(self, pm, genome):
        """Promote key learning to reflection/learnings/ for memory system."""
        if not pm.get("key_learning"):
            return

        learning = {
            "learning_id":          str(uuid.uuid4()),
            "derived_from_pm":      pm["postmortem_id"],
            "statement":            pm["key_learning"],
            "type":                 "failure_learning",
            "niche":                genome["niche"],
            "confidence":           0.40,   # Low confidence until confirmed by more data
            "memory_tier":          "mid_term",
            "gene_implicated":      list(pm.get("gene_diagnoses", {}).keys()),
            "recommendation":       pm.get("recommendation", "retry_with_changes"),
            "created_at":           datetime.now(timezone.utc).isoformat(),
        }
        fname = f"learning_{learning['learning_id'][:8]}.json"
        path  = os.path.join(self.root, f"reflection/learnings/{fname}")
        with open(path, "w") as f:
            json.dump(learning, f, indent=2)

    def _save_postmortem(self, pm):
        fname = f"pm_{pm['postmortem_id'][:8]}.json"
        path  = os.path.join(self.root, f"reflection/postmortems/{fname}")
        with open(path, "w") as f:
            json.dump(pm, f, indent=2)

    def _mark_postmortemed(self, genome_id):
        conn = sqlite3.connect(self.db)
        c    = conn.cursor()
        c.execute("UPDATE genomes SET status='postmortemed' WHERE genome_id=?",
                  (genome_id,))
        conn.commit()
        conn.close()

    def _get_weak_genomes(self, slot):
        conn = sqlite3.connect(self.db)
        conn.row_factory = sqlite3.Row
        c    = conn.cursor()
        c.execute("""
            SELECT g.genome_id, g.fitness_score, g.genes, g.niche,
                   COALESCE(
                     (SELECT json_object(
                        'views_48h', fh.views_48h,
                        'avg_view_duration_pct', fh.avg_view_duration_pct,
                        'like_ratio', fh.like_ratio,
                        'comment_depth_score', fh.comment_depth_score
                      ) FROM fitness_history fh WHERE fh.genome_id=g.genome_id LIMIT 1),
                     '{}'
                   ) as fitness_history_json
            FROM genomes g
            WHERE g.channel_slot=?
              AND g.status='evaluated'
              AND g.fitness_score < ?
              AND g.fitness_score > 0
            LIMIT 10
        """, (slot, FITNESS_THRESHOLD))
        rows = [dict(r) for r in c.fetchall()]
        conn.close()
        return rows

    def _call_gemini(self, prompt, max_tokens=600):
        if not self.gemini_key:
            raise ValueError("No Gemini key")
        url  = (f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"gemini-1.5-flash:generateContent?key={self.gemini_key}")
        body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.4,
                                 "responseMimeType": "application/json"}
        }
        r    = requests.post(url, json=body, timeout=30)
        r.raise_for_status()
        text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return text.strip()
