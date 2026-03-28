"""
orchestrator.py — Master pipeline controller for Project Lyra.
Reads channel_map.json and drives: research → select → create → gate → upload → evolve
"""
import argparse
import json
import os
import sys
import traceback
import logging
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("orchestrator")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# ── helpers ──────────────────────────────────────────────────────────────────

def load_json(path):
    with open(os.path.join(ROOT, path)) as f:
        return json.load(f)

def save_json(path, data):
    full = os.path.join(ROOT, path)
    with open(full, "w") as f:
        json.dump(data, f, indent=2)

def log_error(phase, slot, error):
    path = os.path.join(ROOT, "data/error_log.json")
    with open(path) as f:
        errors = json.load(f)
    errors.append({
        "ts": datetime.now(timezone.utc).isoformat(),
        "phase": phase,
        "channel_slot": slot,
        "error": str(error)
    })
    with open(path, "w") as f:
        json.dump(errors, f, indent=2)

def get_gen():
    p = os.path.join(ROOT, "data/.gen_counter")
    with open(p) as f:
        return int(f.read().strip())

def inc_gen():
    n = get_gen() + 1
    with open(os.path.join(ROOT, "data/.gen_counter"), "w") as f:
        f.write(str(n))
    return n

# ── phase runners ─────────────────────────────────────────────────────────────

def run_research():
    log.info("=== PHASE: RESEARCH ===")
    from src.research_agent import ResearchAgent
    agent = ResearchAgent(ROOT)
    channel_map = load_json("data/channel_map.json")
    for ch in channel_map["channels"]:
        if ch["status"] != "active":
            continue
        try:
            agent.run(ch["slot"], ch["niche"])
        except Exception as e:
            log.error(f"Research failed for slot {ch['slot']}: {e}")
            log_error("research", ch["slot"], e)

def run_generate(slot=None):
    log.info("=== PHASE: GENERATE ===")
    from src.topic_selector import TopicSelector
    from src.script_gen import ScriptGenerator
    from src.voice_gen import VoiceGenerator
    from src.asset_gen import AssetGenerator
    from src.video_assembly import VideoAssembler
    from src.thumbnail_gen import ThumbnailGenerator
    from src.title_engine import TitleEngine
    from src.quality_gate import QualityGate
    from src.upload_agent import UploadAgent
    from src.frequency_controller import FrequencyController

    channel_map = load_json("data/channel_map.json")
    niche_config = load_json("data/niche_config.json")
    learning = load_json("data/learning.json")

    channels = channel_map["channels"]
    if slot is not None:
        channels = [c for c in channels if c["slot"] == slot]

    topic_selector = TopicSelector(ROOT)
    script_gen     = ScriptGenerator(ROOT)
    voice_gen      = VoiceGenerator(ROOT)
    asset_gen      = AssetGenerator(ROOT)
    assembler      = VideoAssembler(ROOT)
    thumb_gen      = ThumbnailGenerator(ROOT)
    title_engine   = TitleEngine(ROOT)
    quality_gate   = QualityGate(ROOT)
    uploader       = UploadAgent(ROOT)
    freq_ctrl      = FrequencyController(ROOT)

    gen = get_gen()

    for ch in channels:
        if ch["status"] != "active":
            continue
        s = ch["slot"]
        log.info(f"--- Channel {s}: {ch['name']} ({ch['niche']}) ---")

        try:
            # Frequency check
            if not freq_ctrl.should_publish(s, "long"):
                log.info(f"Slot {s}: Frequency controller says skip (avoid fatigue)")
                continue

            # 1. Select topic
            topic = topic_selector.select(s, ch["niche"])
            if not topic:
                log.warning(f"Slot {s}: No topic available, skipping")
                continue
            log.info(f"Slot {s}: Topic selected → {topic['topic']}")

            # 2. Generate genome for this content
            genome = _build_genome(s, ch["niche"], learning, gen)

            # 3. Generate scripts (long + shorts)
            scripts = script_gen.generate(topic, genome, ch)
            if not scripts:
                log.error(f"Slot {s}: Script generation failed")
                log_error("script_gen", s, "Script generation returned None")
                continue

            # 4. Generate voice audio
            long_audio  = voice_gen.synthesize(scripts["long_script"], s, "long")
            short_audio = voice_gen.synthesize(scripts["shorts_script"], s, "short")

            if not long_audio:
                log.error(f"Slot {s}: Voice generation failed — no audio produced")
                log_error("voice_gen", s, "Voice generation returned None for long audio")
                continue

            # 5. Generate visuals
            long_frames  = asset_gen.generate_frames(scripts["long_scenes"], s, "long")
            short_frames = asset_gen.generate_frames(scripts["short_scenes"], s, "short")

            # 6. Assemble videos
            long_video  = assembler.assemble(long_frames, long_audio, scripts["long_scenes"],
                                             genome, s, "long")
            short_video = assembler.assemble(short_frames, short_audio, scripts["short_scenes"],
                                             genome, s, "short")

            if not long_video:
                log.error(f"Slot {s}: Video assembly failed — no video produced")
                log_error("video_assembly", s, "Video assembly returned None")
                continue

            # 7. Thumbnail
            thumbnail = thumb_gen.create(long_frames[0] if long_frames else None,
                                         scripts["thumbnail_text"], s, ch["niche"])

            # 8. Title & Description
            metadata = title_engine.generate(topic, genome, ch, niche_config)

            # 9. Quality Gate — ALL 7 gates
            gate_result = quality_gate.check_all(
                script=scripts["long_script"],
                audio_path=long_audio,
                video_path=long_video,
                thumbnail_path=thumbnail,
                title=metadata["title"],
                topic=topic,
                genome=genome
            )

            if not gate_result["passed"]:
                log.warning(f"Slot {s}: Quality gate FAILED → {gate_result['failures']}")
                _save_brief(s, topic, genome, metadata, "gate_failed", gate_result["failures"])
                continue

            log.info(f"Slot {s}: Quality gate PASSED ✓")

            # 10. Upload long video
            long_vid_id = uploader.upload(
                video_path=long_video,
                thumbnail_path=thumbnail,
                title=metadata["title"],
                description=metadata["description"],
                tags=metadata["tags"],
                channel_slot=s,
                video_type="long"
            )

            # 11. Upload short (if exists)
            short_vid_id = None
            if short_video and freq_ctrl.should_publish(s, "short"):
                short_metadata = title_engine.generate_shorts(topic, genome, ch)
                short_thumb    = thumb_gen.create_shorts(short_frames[0] if short_frames else None,
                                                          scripts["thumbnail_text"], s, ch["niche"])
                short_vid_id = uploader.upload(
                    video_path=short_video,
                    thumbnail_path=short_thumb,
                    title=short_metadata["title"],
                    description=short_metadata["description"],
                    tags=short_metadata["tags"],
                    channel_slot=s,
                    video_type="short"
                )

            # 12. Save genome to DB
            _save_genome(genome, long_vid_id, short_vid_id, s, gen)
            _update_channel_stats(s, learning)
            save_json("data/learning.json", learning)

            # 13. Save publish log
            _save_publish_log(s, long_vid_id, short_vid_id, topic, metadata, genome, gen)

            log.info(f"Slot {s}: SUCCESS — Long: {long_vid_id} | Short: {short_vid_id}")

        except Exception as e:
            log.error(f"Slot {s}: Pipeline crashed → {e}")
            log.debug(traceback.format_exc())
            log_error("generate", s, traceback.format_exc())

def run_evolve():
    log.info("=== PHASE: EVOLVE ===")
    from src.analytics_agent import AnalyticsAgent
    from src.evolution_engine import EvolutionEngine
    from src.postmortem_engine import PostmortemEngine
    from src.memory_manager import MemoryManager

    channel_map = load_json("data/channel_map.json")
    analytics   = AnalyticsAgent(ROOT)
    evolution   = EvolutionEngine(ROOT)
    postmortem  = PostmortemEngine(ROOT)
    memory      = MemoryManager(ROOT)

    for ch in channel_map["channels"]:
        if ch["status"] != "active":
            continue
        s = ch["slot"]
        try:
            log.info(f"Evolving slot {s}...")
            analytics.pull_and_score(s)
            postmortem.run_for_slot(s)
            evolution.evolve(s)
            memory.process_tier_promotions(s)
        except Exception as e:
            log.error(f"Evolution failed for slot {s}: {e}")
            log_error("evolve", s, e)

    gen = inc_gen()
    log.info(f"Evolution complete. New generation: {gen}")

# ── internal helpers ──────────────────────────────────────────────────────────

def _build_genome(slot, niche, learning, gen):
    import random, uuid
    allele_pool = load_json("data/allele_pool.json")

    def sample(gene):
        values = allele_pool[gene]["values"]
        priors = allele_pool[gene]["priors"]
        # Weight by priors, bias toward champion alleles
        champion = learning["champion_alleles"].get(gene)
        weights = []
        for v in values:
            w = priors.get(str(v), 1.0 / len(values))
            if champion and str(v) == str(champion):
                w *= 2.0  # 2x weight for champion allele
            penalized = learning["penalized_alleles"].get(gene)
            if penalized and str(v) == str(penalized):
                w *= 0.3  # 0.3x weight for penalized allele
            weights.append(w)
        total = sum(weights)
        weights = [w / total for w in weights]
        return random.choices(values, weights=weights, k=1)[0]

    # Epsilon-greedy: sometimes sample purely random
    eps = learning.get("epsilon", 0.3)
    if random.random() < eps:
        genes = {gene: random.choice(allele_pool[gene]["values"]) for gene in allele_pool}
    else:
        genes = {gene: sample(gene) for gene in allele_pool}

    return {
        "genome_id": str(uuid.uuid4()),
        "channel_slot": slot,
        "niche": niche,
        "generation": gen,
        "parent_ids": [],
        "genes": genes,
        "created_at": datetime.now(timezone.utc).isoformat()
    }

def _save_genome(genome, long_vid_id, short_vid_id, slot, gen):
    import sqlite3
    conn = sqlite3.connect(os.path.join(ROOT, "data/genome.db"))
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO genomes
        (genome_id, channel_slot, niche, generation, parent_ids, status, video_type,
         video_id_youtube, fitness_score, genes, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, (
        genome["genome_id"], slot, genome["niche"], gen,
        json.dumps(genome["parent_ids"]), "published", "long",
        long_vid_id or "", 0.0,
        json.dumps(genome["genes"]),
        genome["created_at"]
    ))
    conn.commit()
    conn.close()

def _update_channel_stats(slot, learning):
    s = str(slot)
    if s not in learning["channel_performance"]:
        learning["channel_performance"][s] = {"avg_fitness": 0.0, "total_videos": 0,
                                               "last_upload": None, "upload_days_this_week": 0}
    learning["channel_performance"][s]["total_videos"] += 1
    learning["channel_performance"][s]["last_upload"] = datetime.now(timezone.utc).isoformat()

def _save_brief(slot, topic, genome, metadata, status, notes):
    import uuid
    brief = {
        "brief_id": str(uuid.uuid4()),
        "slot": slot,
        "topic": topic,
        "genome_id": genome["genome_id"],
        "metadata": metadata,
        "status": status,
        "notes": notes,
        "ts": datetime.now(timezone.utc).isoformat()
    }
    path = os.path.join(ROOT, f"creation/briefs/brief_{brief['brief_id'][:8]}.json")
    with open(path, "w") as f:
        json.dump(brief, f, indent=2)

def _save_publish_log(slot, long_vid_id, short_vid_id, topic, metadata, genome, gen):
    log_entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "slot": slot,
        "generation": gen,
        "genome_id": genome["genome_id"],
        "long_video_id": long_vid_id,
        "short_video_id": short_vid_id,
        "title": metadata.get("title", ""),
        "topic": topic.get("topic", ""),
        "niche": genome["niche"]
    }
    fname = f"publish_{datetime.now().strftime('%Y%m%d_%H%M%S')}_slot{slot}.json"
    path = os.path.join(ROOT, f"execution/publish_logs/{fname}")
    with open(path, "w") as f:
        json.dump(log_entry, f, indent=2)

# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Project Lyra Orchestrator")
    parser.add_argument("--phase", required=True,
                        choices=["research", "generate", "evolve", "full_cycle"],
                        help="Pipeline phase to run")
    parser.add_argument("--channel_slot", type=int, default=None,
                        help="Run only for this channel slot")
    args = parser.parse_args()

    log.info(f"Starting Lyra | Phase: {args.phase} | Slot: {args.channel_slot} | "
             f"Gen: {get_gen()} | {datetime.now(timezone.utc).isoformat()}")

    if args.phase == "research":
        run_research()
    elif args.phase == "generate":
        run_generate(args.channel_slot)
    elif args.phase == "evolve":
        run_evolve()
    elif args.phase == "full_cycle":
        run_research()
        run_generate(args.channel_slot)

if __name__ == "__main__":
    main()
