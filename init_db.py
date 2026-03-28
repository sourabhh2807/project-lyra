"""
init_db.py — Run ONCE before first deployment.
Creates genome.db with all required tables.
"""
import sqlite3
import os
import json

DB_PATH = "data/genome.db"

def init():
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS genomes (
        genome_id TEXT PRIMARY KEY,
        channel_slot INTEGER NOT NULL,
        niche TEXT NOT NULL,
        generation INTEGER NOT NULL,
        parent_ids TEXT DEFAULT '[]',
        status TEXT DEFAULT 'draft',
        video_type TEXT DEFAULT 'long',
        video_id_youtube TEXT DEFAULT '',
        fitness_score REAL DEFAULT 0.0,
        genes TEXT NOT NULL,
        created_at TEXT NOT NULL,
        evaluated_at TEXT DEFAULT ''
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS fitness_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        genome_id TEXT NOT NULL,
        channel_slot INTEGER NOT NULL,
        video_id_youtube TEXT NOT NULL,
        video_type TEXT NOT NULL,
        views_48h INTEGER DEFAULT 0,
        ctr_pct REAL DEFAULT 0.0,
        avg_view_duration_pct REAL DEFAULT 0.0,
        retention_stability REAL DEFAULT 0.0,
        like_ratio REAL DEFAULT 0.0,
        comment_count INTEGER DEFAULT 0,
        comment_depth_score REAL DEFAULT 0.0,
        satisfaction_score REAL DEFAULT 0.0,
        composite_fitness REAL DEFAULT 0.0,
        hook_strength_score REAL DEFAULT 0.0,
        mid_collapse_score REAL DEFAULT 0.0,
        payoff_fulfillment_score REAL DEFAULT 0.0,
        evaluated_at TEXT NOT NULL
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS allele_stats (
        gene_name TEXT NOT NULL,
        allele_value TEXT NOT NULL,
        channel_slot INTEGER NOT NULL,
        total_uses INTEGER DEFAULT 0,
        wins INTEGER DEFAULT 0,
        win_rate REAL DEFAULT 0.0,
        last_updated TEXT NOT NULL,
        PRIMARY KEY (gene_name, allele_value, channel_slot)
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS hypotheses (
        hypothesis_id TEXT PRIMARY KEY,
        channel_slot INTEGER NOT NULL,
        statement TEXT NOT NULL,
        gene_name TEXT NOT NULL,
        allele_a TEXT NOT NULL,
        allele_b TEXT NOT NULL,
        status TEXT DEFAULT 'testing',
        created_generation INTEGER NOT NULL,
        sample_size INTEGER DEFAULT 0,
        allele_a_fitness REAL DEFAULT 0.0,
        allele_b_fitness REAL DEFAULT 0.0,
        result TEXT DEFAULT '',
        promoted_to_rule INTEGER DEFAULT 0,
        created_at TEXT NOT NULL
    )""")

    c.execute("""
    CREATE TABLE IF NOT EXISTS postmortems (
        postmortem_id TEXT PRIMARY KEY,
        genome_id TEXT NOT NULL,
        video_id_youtube TEXT NOT NULL,
        fitness_score REAL NOT NULL,
        failure_reasons TEXT DEFAULT '[]',
        drop_location TEXT DEFAULT '',
        wrong_assumptions TEXT DEFAULT '[]',
        next_tests TEXT DEFAULT '[]',
        recommendation TEXT DEFAULT '',
        knowledge_extracted TEXT DEFAULT '',
        created_at TEXT NOT NULL
    )""")

    conn.commit()
    conn.close()
    print(f"[INIT] genome.db created at {DB_PATH}")

    # Create gen counter
    if not os.path.exists("data/.gen_counter"):
        with open("data/.gen_counter", "w") as f:
            f.write("0")
        print("[INIT] Generation counter initialized at 0")

    # Create memory index
    memory_index = {"short_term": [], "mid_term": [], "long_term": [], "evergreen": []}
    with open("memory/memory_index.json", "w") as f:
        json.dump(memory_index, f, indent=2)
    print("[INIT] Memory index created")

    print("[INIT] Database initialization complete. System ready.")

if __name__ == "__main__":
    init()
