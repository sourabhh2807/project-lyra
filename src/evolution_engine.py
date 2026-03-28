"""
evolution_engine.py — Darwinian genetic engine for Project Lyra.
Runs after analytics: selects winners, crosses genes, mutates alleles,
promotes champions, penalizes losers. Updates allele_pool.json + learning.json.
"""
import os, json, sqlite3, logging, random, math
from datetime import datetime, timezone

log = logging.getLogger("evolution_engine")

class EvolutionEngine:
    def __init__(self, root):
        self.root = root
        self.db   = os.path.join(root, "data/genome.db")

    def evolve(self, slot):
        """Full evolution cycle for one channel slot."""
        genomes = self._get_evaluated_genomes(slot)
        if len(genomes) < 4:
            log.info(f"Slot {slot}: Only {len(genomes)} evaluated genomes — "
                     f"need ≥4 to evolve. Skipping.")
            return

        log.info(f"Slot {slot}: Evolving {len(genomes)} genomes")

        # 1. Rank by fitness
        genomes.sort(key=lambda g: g["fitness_score"], reverse=True)

        # 2. Update allele win rates
        self._update_allele_stats(genomes, slot)

        # 3. Promote champion alleles + penalize weak alleles
        self._update_champion_penalized(genomes)

        # 4. Decay epsilon (exploit more as we learn more)
        self._decay_epsilon()

        # 5. Log generation summary
        avg   = sum(g["fitness_score"] for g in genomes) / len(genomes)
        best  = genomes[0]["fitness_score"]
        worst = genomes[-1]["fitness_score"]
        log.info(f"  Gen summary: best={best:.3f} avg={avg:.3f} worst={worst:.3f}")
        self._save_generation_summary(slot, genomes, avg, best, worst)

    # ── allele statistics ─────────────────────────────────────────────────────

    def _update_allele_stats(self, genomes, slot):
        """Update per-allele win rates in DB and allele_pool.json."""
        conn = sqlite3.connect(self.db)
        c    = conn.cursor()
        now  = datetime.now(timezone.utc).isoformat()

        # Threshold: top 40% = win
        fitness_vals = [g["fitness_score"] for g in genomes]
        fitness_vals.sort(reverse=True)
        win_threshold = fitness_vals[max(0, int(len(fitness_vals) * 0.4) - 1)]

        for genome in genomes:
            genes   = json.loads(genome["genes"])
            is_win  = genome["fitness_score"] >= win_threshold

            for gene_name, allele_val in genes.items():
                c.execute("""
                    INSERT INTO allele_stats
                    (gene_name, allele_value, channel_slot, total_uses, wins,
                     win_rate, last_updated)
                    VALUES (?,?,?,1,?,?,?)
                    ON CONFLICT(gene_name, allele_value, channel_slot) DO UPDATE SET
                        total_uses = total_uses + 1,
                        wins       = wins + ?,
                        win_rate   = CAST(wins + ? AS REAL) / (total_uses + 1),
                        last_updated = ?
                """, (gene_name, str(allele_val), slot,
                      1 if is_win else 0, win_threshold,
                      now,
                      1 if is_win else 0, 1 if is_win else 0, now))

        conn.commit()
        conn.close()

        # Update allele_pool.json priors based on win rates
        self._refresh_allele_priors(slot)

    def _refresh_allele_priors(self, slot):
        """Recalculate allele prior weights from accumulated win rates."""
        pool_path = os.path.join(self.root, "data/allele_pool.json")
        with open(pool_path) as f:
            pool = json.load(f)

        conn = sqlite3.connect(self.db)
        c    = conn.cursor()

        for gene_name in pool:
            c.execute("""
                SELECT allele_value, win_rate, total_uses
                FROM allele_stats
                WHERE gene_name=? AND channel_slot=? AND total_uses >= 3
                ORDER BY win_rate DESC
            """, (gene_name, slot))
            rows = c.fetchall()
            if not rows:
                continue

            # Softmax on win_rates to get new priors
            win_rates = [max(0.01, r[1]) for r in rows]
            total     = sum(win_rates)
            new_priors = {}
            for row, wr in zip(rows, win_rates):
                new_priors[str(row[0])] = round(wr / total, 4)

            # Only update alleles we have stats for (leave others unchanged)
            for allele, prior in new_priors.items():
                if allele in pool[gene_name]["priors"]:
                    # Blend 70% new data, 30% old prior (avoid overfit on small N)
                    old_prior = pool[gene_name]["priors"][allele]
                    pool[gene_name]["priors"][allele] = round(
                        0.70 * prior + 0.30 * old_prior, 4
                    )

        conn.close()
        with open(pool_path, "w") as f:
            json.dump(pool, f, indent=2)

    # ── champion / penalized management ──────────────────────────────────────

    def _update_champion_penalized(self, genomes):
        """Identify champion alleles (top 20%) and penalized alleles (bottom 20%)."""
        learning_path = os.path.join(self.root, "data/learning.json")
        with open(learning_path) as f:
            learning = json.load(f)

        n          = len(genomes)
        top_n      = max(1, int(n * 0.20))
        bottom_n   = max(1, int(n * 0.20))
        top_genomes    = genomes[:top_n]
        bottom_genomes = genomes[-bottom_n:]

        # Champion: allele that appears most in top genomes
        champion_votes = {}
        for g in top_genomes:
            genes = json.loads(g["genes"])
            for gene, allele in genes.items():
                k = f"{gene}:{allele}"
                champion_votes[k] = champion_votes.get(k, 0) + 1

        # Penalized: allele that appears most in bottom genomes
        penalty_votes = {}
        for g in bottom_genomes:
            genes = json.loads(g["genes"])
            for gene, allele in genes.items():
                k = f"{gene}:{allele}"
                penalty_votes[k] = penalty_votes.get(k, 0) + 1

        # Promote top champion per gene
        pool_path = os.path.join(self.root, "data/allele_pool.json")
        with open(pool_path) as f:
            pool = json.load(f)

        for gene_name in pool:
            # Find best allele for this gene among top genomes
            best_allele = None
            best_votes  = 0
            for allele in pool[gene_name]["values"]:
                k = f"{gene_name}:{allele}"
                if champion_votes.get(k, 0) > best_votes:
                    best_votes  = champion_votes.get(k, 0)
                    best_allele = allele

            if best_allele and best_votes >= 2:
                learning["champion_alleles"][gene_name] = best_allele

            # Penalize worst allele for this gene
            worst_allele = None
            worst_votes  = 0
            for allele in pool[gene_name]["values"]:
                k = f"{gene_name}:{allele}"
                if penalty_votes.get(k, 0) > worst_votes:
                    worst_votes  = penalty_votes.get(k, 0)
                    worst_allele = allele

            if worst_allele and worst_votes >= 2:
                learning["penalized_alleles"][gene_name] = worst_allele

        with open(learning_path, "w") as f:
            json.dump(learning, f, indent=2)
        log.info(f"  Champion alleles: {learning['champion_alleles']}")

    # ── epsilon decay ─────────────────────────────────────────────────────────

    def _decay_epsilon(self):
        """Decay exploration rate toward minimum."""
        learning_path = os.path.join(self.root, "data/learning.json")
        with open(learning_path) as f:
            learning = json.load(f)

        eps     = learning.get("epsilon", 0.30)
        eps_min = learning.get("epsilon_min", 0.05)
        decay   = learning.get("epsilon_decay", 0.005)

        new_eps = max(eps_min, eps - decay)
        learning["epsilon"] = round(new_eps, 4)
        learning["last_evolution_generation"] = self._get_gen()

        with open(learning_path, "w") as f:
            json.dump(learning, f, indent=2)
        log.info(f"  Epsilon: {eps:.3f} → {new_eps:.3f}")

    # ── helpers ───────────────────────────────────────────────────────────────

    def _get_evaluated_genomes(self, slot):
        conn = sqlite3.connect(self.db)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("""
            SELECT genome_id, fitness_score, genes, niche, generation
            FROM genomes
            WHERE channel_slot=? AND status='evaluated'
            ORDER BY created_at DESC
            LIMIT 100
        """, (slot,))
        rows = [dict(r) for r in c.fetchall()]
        conn.close()
        return rows

    def _save_generation_summary(self, slot, genomes, avg, best, worst):
        summary = {
            "ts":       datetime.now(timezone.utc).isoformat(),
            "slot":     slot,
            "gen":      self._get_gen(),
            "n":        len(genomes),
            "avg":      round(avg, 4),
            "best":     round(best, 4),
            "worst":    round(worst, 4),
        }
        path = os.path.join(self.root,
                            f"reflection/learnings/gen_summary_{summary['gen']}_slot{slot}.json")
        with open(path, "w") as f:
            json.dump(summary, f, indent=2)

    def _get_gen(self):
        try:
            with open(os.path.join(self.root, "data/.gen_counter")) as f:
                return int(f.read().strip())
        except Exception:
            return 0
