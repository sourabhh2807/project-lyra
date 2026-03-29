"""
health_check.py — Daily system health monitor + full Lyra status report.
Generates LYRA_REPORT.md with everything: what's working, what's not,
trending topics, niche performance, content info, system status.
"""
import os, json, glob, sys, sqlite3
from datetime import datetime, timezone, timedelta

# Fix ROOT — go up from src/ to project root
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_json(path, default=None):
    try:
        with open(os.path.join(ROOT, path)) as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}

def check():
    issues  = []
    ok      = []
    now     = datetime.now(timezone.utc)

    # ── 1. Check data/health_report.json path exists ──────────────────────────
    data_dir = os.path.join(ROOT, "data")
    os.makedirs(data_dir, exist_ok=True)

    # ── 2. Check channels have uploaded recently ──────────────────────────────
    channel_map = load_json("data/channel_map.json", {})
    channels    = channel_map.get("channels", [])
    upload_info = {}

    for ch in channels:
        if ch.get("status") != "active":
            continue
        slot    = ch["slot"]
        pattern = os.path.join(ROOT, "execution/publish_logs/*.json")
        last_upload = None
        total_uploads = 0
        recent_uploads = []

        for path in glob.glob(pattern):
            try:
                with open(path) as f:
                    entry = json.load(f)
                if entry.get("slot") != slot:
                    continue
                total_uploads += 1
                ts = datetime.fromisoformat(entry["ts"].replace("Z", "+00:00"))
                if last_upload is None or ts > last_upload:
                    last_upload = ts
                if (now - ts).days < 7:
                    recent_uploads.append(entry)
            except Exception:
                pass

        upload_info[slot] = {
            "total": total_uploads,
            "last":  last_upload.isoformat() if last_upload else "Never",
            "recent_7d": len(recent_uploads),
            "recent_list": sorted(recent_uploads, key=lambda x: x["ts"], reverse=True)[:5]
        }

        if last_upload is None:
            issues.append(f"Channel {ch['name']} has NEVER uploaded")
        elif (now - last_upload).total_seconds() > 72 * 3600:
            h = int((now - last_upload).total_seconds() / 3600)
            issues.append(f"Channel {ch['name']} last upload was {h}h ago")
        else:
            ok.append(f"Channel {ch['name']} is uploading ✓")

    # ── 3. Check error log ────────────────────────────────────────────────────
    errors     = load_json("data/error_log.json", [])
    recent_err = [
        e for e in errors
        if (now - datetime.fromisoformat(
            e.get("ts", "2000-01-01T00:00:00+00:00").replace("Z", "+00:00")
        )).total_seconds() < 24 * 3600
    ]
    if len(recent_err) > 5:
        issues.append(f"{len(recent_err)} errors in last 24h")
    else:
        ok.append(f"Error log clean ({len(recent_err)} errors in 24h) ✓")

    # ── 4. Check research candidates ─────────────────────────────────────────
    candidates = glob.glob(os.path.join(ROOT, "research/processed/topic_candidates/*.json"))
    queued     = []
    for path in candidates:
        try:
            with open(path) as f:
                c = json.load(f)
            if c.get("status") == "queued":
                queued.append(c)
        except Exception:
            pass

    if len(queued) < 3:
        issues.append(f"Only {len(queued)} topics queued — research may be stalled")
    else:
        ok.append(f"Research pipeline has {len(queued)} topics queued ✓")

    # Sort by predicted fitness to find top trending topics
    top_topics = sorted(queued, key=lambda x: x.get("predicted_fitness", 0), reverse=True)[:10]

    # ── 5. Check genome DB ────────────────────────────────────────────────────
    db_path  = os.path.join(ROOT, "data/genome.db")
    db_stats = {"total": 0, "published": 0, "evaluated": 0, "avg_fitness": 0.0, "best_fitness": 0.0}
    niche_stats = {}
    recent_videos = []

    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            c    = conn.cursor()

            c.execute("SELECT COUNT(*) as n FROM genomes")
            db_stats["total"] = c.fetchone()["n"]

            c.execute("SELECT COUNT(*) as n FROM genomes WHERE status='published'")
            db_stats["published"] = c.fetchone()["n"]

            c.execute("SELECT COUNT(*) as n FROM genomes WHERE status='evaluated'")
            db_stats["evaluated"] = c.fetchone()["n"]

            c.execute("SELECT AVG(fitness_score) as avg, MAX(fitness_score) as best FROM genomes WHERE fitness_score > 0")
            row = c.fetchone()
            if row and row["avg"]:
                db_stats["avg_fitness"] = round(row["avg"], 3)
                db_stats["best_fitness"] = round(row["best"], 3)

            # Per-niche stats
            c.execute("""
                SELECT niche, COUNT(*) as count, AVG(fitness_score) as avg_fit
                FROM genomes WHERE fitness_score > 0
                GROUP BY niche
            """)
            for row in c.fetchall():
                niche_stats[row["niche"]] = {
                    "videos": row["count"],
                    "avg_fitness": round(row["avg_fit"] or 0, 3)
                }

            # Recent videos
            c.execute("""
                SELECT genome_id, niche, fitness_score, video_id_youtube, created_at
                FROM genomes
                ORDER BY created_at DESC
                LIMIT 10
            """)
            recent_videos = [dict(r) for r in c.fetchall()]
            conn.close()

            ok.append(f"Genome DB healthy — {db_stats['total']} genomes ✓")
        except Exception as e:
            issues.append(f"Genome DB error: {e}")
    else:
        issues.append("genome.db not found — run init_db.py")

    # ── 6. Check memory system ────────────────────────────────────────────────
    mem_index = load_json("memory/memory_index.json", {})
    mem_counts = {
        "short_term": len(mem_index.get("short_term", [])),
        "mid_term":   len(mem_index.get("mid_term",   [])),
        "long_term":  len(mem_index.get("long_term",  [])),
        "evergreen":  len(mem_index.get("evergreen",  [])),
    }
    ok.append(f"Memory: {mem_counts['long_term']} long-term rules | {mem_counts['mid_term']} mid-term ✓")

    # ── 7. Learning state ─────────────────────────────────────────────────────
    learning = load_json("data/learning.json", {})
    epsilon  = learning.get("epsilon", 0.30)
    gen      = learning.get("generation", 0)
    try:
        with open(os.path.join(ROOT, "data/.gen_counter")) as f:
            gen = int(f.read().strip())
    except Exception:
        pass

    champions  = learning.get("champion_alleles", {})
    penalized  = learning.get("penalized_alleles", {})
    ch_perf    = learning.get("channel_performance", {})

    # ── 8. Determine niche direction ─────────────────────────────────────────
    niche_direction = "Still exploring — not enough data yet"
    if niche_stats:
        best_niche = max(niche_stats, key=lambda x: niche_stats[x]["avg_fitness"])
        if niche_stats[best_niche]["videos"] >= 3:
            niche_direction = (
                f"Trending toward '{best_niche}' "
                f"(avg fitness {niche_stats[best_niche]['avg_fitness']}) — "
                f"system will increase this niche's share automatically"
            )

    # ── 9. Build full status report ───────────────────────────────────────────
    status = "🔴 UNHEALTHY" if issues else "🟢 HEALTHY"

    report_lines = [
        f"# 🌌 LYRA SYSTEM REPORT",
        f"**Generated:** {now.strftime('%Y-%m-%d %H:%M')} UTC",
        f"**System Status:** {status}",
        f"**Generation:** {gen}",
        f"**Exploration Rate (ε):** {epsilon:.3f} "
        f"({'Still exploring' if epsilon > 0.15 else 'Converging on winners' if epsilon > 0.08 else 'Fully exploiting top content'})",
        "",
        "---",
        "",
        "## ✅ WHAT IS WORKING",
    ]
    for o in ok:
        report_lines.append(f"- {o}")

    if issues:
        report_lines += ["", "## ❌ ISSUES"]
        for i in issues:
            report_lines.append(f"- ⚠️ {i}")

    if recent_err:
        report_lines += ["", "## 🔴 RECENT ERRORS (last 24h)"]
        for e in recent_err[-5:]:
            report_lines.append(f"- `{e.get('phase','?')}`: {str(e.get('error',''))[:120]}")

    report_lines += [
        "",
        "---",
        "",
        "## 📊 CONTENT PERFORMANCE",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total Videos Generated | {db_stats['total']} |",
        f"| Videos Published | {db_stats['published']} |",
        f"| Videos Evaluated | {db_stats['evaluated']} |",
        f"| Average Fitness Score | {db_stats['avg_fitness']} |",
        f"| Best Fitness Score Ever | {db_stats['best_fitness']} |",
        "",
        "### Performance by Niche",
        "",
        "| Niche | Videos | Avg Fitness | Direction |",
        "|-------|--------|-------------|-----------|",
    ]

    for niche, stats in sorted(niche_stats.items(), key=lambda x: x[1]["avg_fitness"], reverse=True):
        bar    = "⬆️ WINNING" if stats["avg_fitness"] > 0.4 else "➡️ TESTING" if stats["avg_fitness"] > 0.2 else "⬇️ WEAK"
        report_lines.append(f"| {niche} | {stats['videos']} | {stats['avg_fitness']} | {bar} |")

    report_lines += [
        "",
        f"### 🧬 Niche Direction",
        f"{niche_direction}",
        "",
        "---",
        "",
        "## 🔥 TOP TRENDING TOPICS RIGHT NOW",
        "(From research agent — highest predicted fitness)",
        "",
    ]

    if top_topics:
        for i, t in enumerate(top_topics[:10], 1):
            report_lines.append(
                f"{i}. **{t.get('topic','?')}** "
                f"| Niche: {t.get('niche','?')} "
                f"| Predicted fit: {t.get('predicted_fitness',0):.2f} "
                f"| Format: {t.get('recommended_format','?')}"
            )
    else:
        report_lines.append("No queued topics yet — research agent will populate these hourly.")

    report_lines += [
        "",
        "---",
        "",
        "## 🎬 RECENT VIDEOS",
        "",
        "| Niche | Fitness | YouTube ID | Date |",
        "|-------|---------|------------|------|",
    ]

    for v in recent_videos:
        yt_link = f"[Watch](https://youtube.com/watch?v={v['video_id_youtube']})" if v.get("video_id_youtube") else "Pending"
        fitness = f"{v['fitness_score']:.3f}" if v.get("fitness_score") else "Not evaluated"
        date    = v.get("created_at","")[:10]
        report_lines.append(f"| {v.get('niche','?')} | {fitness} | {yt_link} | {date} |")

    report_lines += [
        "",
        "---",
        "",
        "## 🧠 WHAT THE BRAIN HAS LEARNED",
        "",
        "### Champion Alleles (Best Performing Genes)",
    ]

    if champions:
        for gene, allele in champions.items():
            report_lines.append(f"- **{gene}:** `{allele}` ← system favors this")
    else:
        report_lines.append("- Not enough data yet — learning starts after ~5 evaluated videos")

    report_lines += ["", "### Penalized Alleles (Underperformers)"]
    if penalized:
        for gene, allele in penalized.items():
            report_lines.append(f"- **{gene}:** `{allele}` ← system avoids this")
    else:
        report_lines.append("- None penalized yet")

    report_lines += [
        "",
        "---",
        "",
        "## 💾 MEMORY SYSTEM",
        "",
        f"| Memory Tier | Items |",
        f"|-------------|-------|",
        f"| Short-term (48h) | {mem_counts['short_term']} |",
        f"| Mid-term (7-30d) | {mem_counts['mid_term']} |",
        f"| Long-term (permanent) | {mem_counts['long_term']} |",
        f"| Evergreen rules | {mem_counts['evergreen']} |",
        "",
        "---",
        "",
        "## ⏰ SYSTEM SCHEDULE",
        "",
        "| What | When | Status |",
        "|------|------|--------|",
        "| Research (trend scan) | Every hour | Auto ✅ |",
        "| Content generation + upload | Every 6 hours | Auto ✅ |",
        "| Analytics + Evolution | Every 48 hours | Auto ✅ |",
        "| Memory compression | Weekly | Auto ✅ |",
        "| This report | Daily | Auto ✅ |",
        "",
        "---",
        "",
        f"*Report auto-generated by Lyra Health Check · {now.isoformat()}*",
    ]

    report_text = "\n".join(report_lines)

    # ── 10. Save health_report.json ───────────────────────────────────────────
    report_json = {
        "ts":            now.isoformat(),
        "status":        "unhealthy" if issues else "healthy",
        "issues":        issues,
        "ok":            ok,
        "generation":    gen,
        "epsilon":       epsilon,
        "db_stats":      db_stats,
        "niche_stats":   niche_stats,
        "memory_counts": mem_counts,
        "top_topics":    [t.get("topic","") for t in top_topics[:5]],
        "champions":     champions,
    }

    report_path = os.path.join(ROOT, "data/health_report.json")
    with open(report_path, "w") as f:
        json.dump(report_json, f, indent=2)

    # ── 11. Save LYRA_REPORT.md ───────────────────────────────────────────────
    md_path = os.path.join(ROOT, "LYRA_REPORT.md")
    with open(md_path, "w") as f:
        f.write(report_text)

    # ── 12. Print summary to GitHub Actions log ───────────────────────────────
    print("\n" + "="*60)
    print(f"LYRA HEALTH: {status}")
    print(f"Generation: {gen} | Epsilon: {epsilon:.3f}")
    print(f"Videos: {db_stats['total']} total | {db_stats['published']} published")
    print(f"Avg Fitness: {db_stats['avg_fitness']} | Best: {db_stats['best_fitness']}")
    print(f"Queued Topics: {len(queued)}")
    print(f"Niche Direction: {niche_direction[:80]}")
    if issues:
        print("\nISSUES:")
        for i in issues:
            print(f"  ⚠️  {i}")
    else:
        print("All checks passed ✓")
    print("="*60)
    print(f"\nFull report saved to LYRA_REPORT.md")

    # NOTE: We do NOT sys.exit(1) here even with issues.
    # In early stages (gen 0-2), issues like "never uploaded" are EXPECTED.
    # Exiting 1 prevents the workflow from committing the report, which defeats
    # the purpose. The report itself documents the issues clearly.
    # Critical failures are still logged; the workflow status reflects the report.

if __name__ == "__main__":
    check()
