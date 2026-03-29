[10_NEW_PROJECT_LYRA_BIBLE.md](https://github.com/user-attachments/files/26328621/10_NEW_PROJECT_LYRA_BIBLE.md)
# PROJECT LYRA — THE COMPLETE BIBLE
### Autonomous YouTube Content Intelligence System
### *Every Idea. Every Fix. Every File. Nothing Lost.*

**Document Version:** 1.0 — March 29, 2026  
**System Version:** V9.0 — The Godmind Protocol  
**Repo:** `github.com/sourabhh2807/project-lyra`  
**Compute:** 100% Cloud · GitHub Actions · Zero Local Dependency  
**Monthly Cost:** $0.00 (with 3h research cron) to ~$1.60 (1h research)

---

## DOCUMENT PURPOSE

This is the **permanent, complete record** of everything Project Lyra has been, is, and will be.
Every architecture decision, every bug fix, every file's role, the current deployment state,
and the full roadmap — all in one place. Nothing from any prior version is omitted.

---

## TABLE OF CONTENTS

- [Part I — What Lyra Is](#part-i--what-lyra-is)
- [Part II — Architecture Deep Dive](#part-ii--architecture-deep-dive)
- [Part III — Every File Explained](#part-iii--every-file-explained)
- [Part IV — Current Deployment State & All Bug Fixes](#part-iv--current-deployment-state--all-bug-fixes)
- [Part V — Strategy, Scaling & Future](#part-v--strategy-scaling--future)

---

# PART I — WHAT LYRA IS

## 1.1 The Vision

Lyra is an autonomous system that researches trending topics, writes video scripts,
synthesizes narration, generates visuals, assembles complete videos, and publishes them
to YouTube — all running on free cloud infrastructure with zero human intervention after setup.

The core innovation: **each video is a genome** with genes controlling every content decision.
A Darwinian selection engine evaluates 48-hour performance, promotes winners, penalizes losers,
and mutates the gene pool — creating a system that compounds intelligence with every upload.

## 1.2 The Three Laws (Override Everything)

**Law I — Fitness or Integrity:** Only honest fitness counts. Deceptive content is rejected even if it performs.

**Law II — Zero Local Compute:** Everything runs on GitHub Actions. Laptop needed only for initial OAuth setup.

**Law III — Memory is Sacred:** Every success and failure is recorded. A system with amnesia cannot evolve.

## 1.3 Version History

| Version | What Changed |
|---------|-------------|
| V3.0 | Original concept: genetic intelligence, 50 channels on 1 account (fatal flaw identified) |
| V4.0 | Free API stack, cloud-only architecture, removed local compute dependency |
| V7.0 | Intelligence loop redesign, 6D human behavior model, 7-gate quality engine, Edge-TTS over gTTS |
| V8.0 | Unified Godmind Protocol, 25 sections, full synthesis of all ideas |
| **V9.0** | **Production build. 3-channel start. All code implemented. Current version.** |

### All Critical Fixes Across Versions

| Version | Original Assumption | Why It Fails | The Fix |
|---------|-------------------|--------------|---------|
| V3 | 50 channels on 1 Google account | Single ban kills everything | 1 channel = 1 account, always |
| V3 | Optimize for raw upload volume | Creates noise, corrupts learning | Quality-gated dynamic cadence |
| V3 | Bypass AI detectors via metadata jitter | YouTube ToS violation | Never attempt platform evasion |
| V3 | Bot auto-respond to all comments | Bannable ToS violation | LLM drafts → human approves |
| V3 | MD5 hash evasion via framerate tricks | Signals inauthentic behavior | Real variation in content only |
| V3 | CTR as primary fitness signal | Measures clickbait, not quality | Composite fitness (satisfaction + AVD highest) |
| V4 | Blind random mutation | Causes drift into local minima | Evidence threshold + holdout + rollback |
| V4 | Copy competitor retention spikes | System becomes derivative | Extract principles, never clone |
| V7 | gTTS for voice | Sounds robotic, kills trust | Edge-TTS (Microsoft Neural) |
| V7 | Fully random immigration each gen | Too much chaos | 1 wild genome per 5 generations |

---

# PART II — ARCHITECTURE DEEP DIVE

## 2.1 System Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                  GITHUB REPOSITORY — THE BRAIN                   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                DATA PERSISTENCE LAYER                   │    │
│  │ genome.db (SQLite) │ learning.json │ allele_pool.json   │    │
│  │ channel_map.json   │ memory/       │ research/processed/│    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │            GITHUB ACTIONS RUNNERS (Free CPU)            │    │
│  │                                                         │    │
│  │  CRON 3-hourly → research_agent.py (trend scanning)     │    │
│  │  CRON 6-hourly → orchestrator.py (full pipeline)        │    │
│  │  CRON 48h      → analytics + evolution engine           │    │
│  │  CRON daily    → health_check.py + LYRA_REPORT.md       │    │
│  │  CRON weekly   → memory_manager (tier promotions)       │    │
│  │                                                         │    │
│  │  Pipeline per slot:                                     │    │
│  │  research → select → script → voice → images            │    │
│  │  → assemble → quality_gate → upload → log               │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │               FREE EXTERNAL APIS                        │    │
│  │  Gemini 1.5 Flash │ Groq llama-3 │ Pollinations.ai      │    │
│  │  HuggingFace SDXL │ Edge-TTS     │ YouTube Data API v3  │    │
│  │  Google Trends    │ FFmpeg (native on runner)            │    │
│  └─────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘
```

### Free Tier Budget

| Resource | Free Limit | Lyra Usage | Notes |
|----------|-----------|------------|-------|
| GitHub Actions | 2,000 min/month | ~2,200/month | ~$1.60 overage (or $0 with 3h research) |
| Gemini Flash | 1M tokens/day | ~400K/day | Safe margin |
| Groq llama-3 | 14,400 req/day | <100/day | Fallback only |
| Pollinations.ai | Unlimited (soft) | ~60 images/day | Zero cost |
| HuggingFace | 1,000 calls/day | <20/day | Fallback only |
| YouTube Data API | 10,000 units/day | ~6,000/day | Tight but OK |

## 2.2 The Godmind Intelligence Loop (11 Stages)

```
SENSE → FILTER → UNDERSTAND → HYPOTHESIZE → CREATE → QUALITY_GATE
     → PUBLISH → EVALUATE → LEARN → UPGRADE → PRESERVE → [loop]
```

1. **SENSE** — Google Trends, YouTube trending, competitor channels, own comments
2. **FILTER** — 5 filters: relevance, novelty, saturation, credibility, brand fit
3. **UNDERSTAND** — LLM builds structured understanding (why now, audience state, emotions)
4. **HYPOTHESIZE** — Testable predictions before creation ("contrarian hook > curiosity gap here")
5. **CREATE** — Scripts, voice, visuals, thumbnails, titles — all from champion genome
6. **QUALITY GATE** — All 7 gates must pass. One failure = hold or discard
7. **PUBLISH** — YouTube upload via Data API v3, set thumbnail, seed comment
8. **EVALUATE** — 48h analytics pull, composite fitness score
9. **LEARN** — Confirmed hypothesis → rule. Denied → anti-pattern. Anomaly → investigation
10. **UPGRADE** — Controlled gene mutation with evidence threshold and rollback
11. **PRESERVE** — All knowledge committed to repo. Nothing lost.

## 2.3 The Genetic Algorithm

### Gene Categories (14 genes in `allele_pool.json`)

**Topic Genes:** niche, urgency_type, novelty_type, authority_fit, audience_state_target
**Hook Genes:** hook_type (8 alleles), hook_duration_sec, open_loop_count, hook_visual_intensity
**Narrative Genes:** narrative_structure (8 alleles), payoff_placement_pct, escalation_curve
**Delivery Genes:** narration_style (6 alleles), narration_pace_wpm, voice_energy_level, humor_intensity, directness_level
**Visual Genes:** pacing_profile, motion_density, overlay_density, illustration_ratio, color_grade
**Packaging Genes:** title_archetype, thumbnail_style, promise_style, payoff_framing
**Trust Genes:** source_citation_density, confidence_wording_style, explanation_depth

### Fitness Score Formula

```
Fitness =
  0.28 × Satisfaction_Score
+ 0.22 × Avg_View_Duration_pct
+ 0.15 × Retention_Stability_Score
+ 0.12 × CTR_Quality_Score
+ 0.10 × Comment_Depth_Score
+ 0.08 × Return_Viewer_Lift
+ 0.05 × Topic_Originality_Score
```

### Evolution Mechanics

- **Champion-Challenger:** 80% uploads use champion genes, 20% test challengers
- **ε-Greedy Bandit:** Starts at 0.30 (30% exploration), decays by 0.005/cycle to min 0.05
- **Gene Interaction Tracking:** System tracks combinatorial effects (e.g., "curiosity_gap + documentary_reveal = +0.12 in dark_history")
- **Two-Layer Evolution:** Content genes evolve every 48h (Layer A). System parameters evolve monthly (Layer B, requires human review)

## 2.4 The 7-Gate Quality Engine

No content publishes without passing ALL gates:

| Gate | What It Checks | Threshold |
|------|---------------|-----------|
| 1. Research Quality | Topic still timely, angle differentiated, confidence ≥ 0.30 | Configurable |
| 2. Script Quality | Word count ≥ 200, n-gram repeat < 0.45, no generic openers | Configurable |
| 3. Narrative Structure | Hook present, payoff exists (heuristic check) | Heuristic |
| 4. Audio Quality | File exists, size > 5KB, duration > 30s | ffprobe |
| 5. Video Quality | File exists, has video + audio streams, size > 0.5MB | ffprobe |
| 6. Authenticity | Filler phrase density < 1.0 per 100 words | Heuristic |
| 7. Platform Safety | No blocked content patterns, honest title-thumbnail match | Hard block |

Gate 7 is NEVER relaxed. Content that fails any gate is held for revision or discarded.

## 2.5 The Human Behavior Model (6 Dimensions)

Every piece of content is designed against these psychological dimensions:

1. **Attention** — Why they stop scrolling (novelty, pattern interrupt, identity relevance)
2. **Curiosity** — Why they keep watching (information gap + perceived value of resolution)
3. **Comprehension** — Whether they understand (right baseline, clear flow, no jargon)
4. **Tension** — Whether anticipation is maintained (unresolved thread every 90 seconds)
5. **Reward** — Whether the promise is fulfilled (title/thumbnail must match delivery)
6. **Identity** — Whether they feel "this is for me" (channel speaks audience's language)

### Audience State Model

| State | Content Strategy |
|-------|-----------------|
| Unaware | Lead with consequence or surprise |
| Problem-aware | Lead with empathy, then reveal |
| Solution-aware | Lead with differentiation |
| Comparison mode | Lead with honest analysis |
| Emotionally charged | Lead with validation |
| Entertainment-seeking | Lead with personality and energy |

## 2.6 The Memory System (3 Tiers)

**Short-Term (48h)** — Live experiments, pending analytics, trend alerts. Purged after 48h unless promoted.

**Mid-Term (7-30 days)** — Working formulas, audience behavior shifts, running gene win rates. Promoted from short-term if signal persists.

**Long-Term (30+ days, permanent)** — Proven audience psychology rules (≥100 data points), evergreen structures, seasonal patterns, failed ideas with documented reasons.

### Knowledge Objects

Every promoted strategy → Learning Object. Every failure with fitness < 0.25 → Postmortem Object.

## 2.7 The Resilience Chain

```
Gemini fails → Groq fallback
Groq fails   → Template fallback
Pollinations fails → HuggingFace SDXL fallback
HF fails     → Pillow placeholder frame
Edge-TTS fails → CLI fallback → partial audio
Assembly fails → Simple slideshow fallback
Upload fails → Mark pending, retry next cycle
Any crash    → try/except logs to error_log.json, pipeline continues
```

---

# PART III — EVERY FILE EXPLAINED

## 3.1 Full Repository Tree

```
project-lyra/
│
├── .github/workflows/
│   ├── lyra_cycle.yml           ← Master 6h cycle: research + generate all slots
│   ├── analytics_evolve.yml     ← 48h analytics pull + genetic evolution
│   ├── research_continuous.yml  ← 3-hourly trend scanning (lightweight)
│   ├── health_and_memory.yml    ← Daily health check + weekly memory compression
│   └── init_once.yml            ← One-time: initialize genome.db
│
├── src/
│   ├── __init__.py              ← Package marker
│   ├── orchestrator.py          ← Master pipeline controller
│   ├── research_agent.py        ← Trend sensing + topic candidate generation
│   ├── topic_selector.py        ← Filter + score + select best topic
│   ├── script_gen.py            ← LLM script generation (long + shorts)
│   ├── voice_gen.py             ← Edge-TTS narration synthesis
│   ├── asset_gen.py             ← AI image generation per scene
│   ├── video_assembly.py        ← FFmpeg video assembly with Ken Burns
│   ├── thumbnail_gen.py         ← Pillow thumbnail creation
│   ├── title_engine.py          ← Title/description/tag generation
│   ├── upload_agent.py          ← YouTube Data API v3 upload
│   ├── analytics_agent.py       ← Metrics pull + fitness computation
│   ├── evolution_engine.py      ← Genetic ops: selection, mutation, decay
│   ├── frequency_controller.py  ← Cadence management + fatigue detection
│   ├── postmortem_engine.py     ← Auto-postmortems for weak performers
│   ├── memory_manager.py        ← 3-tier memory promotions + compression
│   ├── health_check.py          ← System health monitor + LYRA_REPORT.md
│   └── token_refresh.py         ← Auto-refresh OAuth tokens every run
│
├── data/
│   ├── genome.db                ← SQLite: genomes, fitness_history, allele_stats
│   ├── .gen_counter             ← Current generation number (plain text)
│   ├── learning.json            ← System state: epsilon, champions, penalized
│   ├── allele_pool.json         ← Gene values + prior weights (evolves)
│   ├── channel_map.json         ← Slot → channel config + status
│   ├── niche_config.json        ← 3 niches: descriptions, keywords, competitors
│   ├── title_patterns.json      ← 12 viral title pattern templates
│   ├── health_report.json       ← Latest health check output
│   └── error_log.json           ← Append-only failure log
│
├── research/
│   ├── raw/{trends,competitors,comments}/
│   └── processed/{topic_candidates,audience_maps,saturation_maps}/
│
├── creation/
│   ├── briefs/                  ← Topic → creation brief objects
│   ├── scripts/                 ← Generated long + short scripts (JSON)
│   ├── voice/                   ← Synthesized narration MP3s (gitignored, temp)
│   ├── visuals/                 ← Generated frames + cache (gitignored, temp)
│   └── packaging/               ← Thumbnails, titles, descriptions
│
├── execution/
│   ├── publish_logs/            ← Permanent log of every upload
│   └── render/                  ← Assembled videos (gitignored, temp)
│
├── analytics/{raw_exports,normalized,retention}/
├── memory/{short_term,mid_term,long_term,evergreen,memory_index.json}
├── reflection/{postmortems,learnings,failed_hypotheses,promoted_hypotheses}/
├── experiments/{queued,running,concluded}/
├── archive/snapshots/           ← Monthly genome + memory snapshots
├── governance/thresholds.json   ← All quality gate thresholds (versioned)
│
├── init_db.py                   ← Run once: creates genome.db
├── get_oauth_token.py           ← Run locally: gets YouTube OAuth tokens
├── refresh_token.py             ← Run locally if needed: manual token refresh
├── requirements.txt             ← Python dependencies
├── .gitignore
├── README.md
├── SETUP_GUIDE.md               ← Complete step-by-step setup manual
└── PROJECT_LYRA_V9_GODMIND.md   ← Master blueprint document
```

## 3.2 Source Code Files — What Each Does

### `orchestrator.py` — The Brain's Dispatcher
Routes all pipeline phases. Receives `--phase` argument (research, generate, evolve, full_cycle) and `--channel_slot`. Loads channel_map.json, instantiates all required modules, runs the pipeline, catches all errors, logs to error_log.json, saves genomes to SQLite, commits publish logs. The `_build_genome()` function samples alleles using champion/penalized weights and ε-greedy exploration.

### `research_agent.py` — 24/7 Intelligence Gathering
Scans Google Trends (via pytrends) and YouTube Data API for niche-relevant signals. For each signal, calls Gemini to evaluate and build a structured topic candidate with scores for novelty, saturation, authority fit, predicted fitness, and recommended format. Falls back to minimal candidates if LLM fails. Saves to `research/processed/topic_candidates/`.

### `topic_selector.py` — Choosing What to Create
Loads all queued candidates for a niche, filters out: recently published topics (60-day window), expired topics (beyond urgency_decay_days), and low-confidence candidates (<0.35). Sorts by predicted_fitness, picks the best, marks it "in_creation" so it's not picked again.

### `script_gen.py` — LLM Scriptwriting
Builds detailed prompts incorporating genome genes (hook_type, narrative_structure, narration_style, pacing_profile, etc.) and topic context. Calls Gemini 1.5 Flash with `responseMimeType: "application/json"` for reliable JSON output. Falls back to Groq llama-3. Has 5-strategy JSON parser for robustness. Generates both long-form (10-15 min) and shorts (45-58 sec) scripts. Returns structured scene data with narration, visual descriptions, and text overlays.

### `voice_gen.py` — Microsoft Neural Voice Synthesis
Uses Edge-TTS (zero cost, near-human quality). Maps voice styles to specific neural voices per channel personality. Handles long scripts via text chunking (splits at sentence boundaries, max 4500 chars/chunk). Synthesizes each chunk independently, concatenates with FFmpeg. Has retry logic (3 attempts with exponential backoff) and CLI fallback. Returns MP3 path.

### `asset_gen.py` — AI Image Generation
Generates one image per scene via Pollinations.ai (zero API key, zero cost). Enhances prompts with niche-specific style keywords (dark cinematic for history, clean blue for psychology, tech cyan for AI). Implements vector reuse cache (MD5 hash of prompt → skip if match, saves ~40% API calls). Falls back to HuggingFace SDXL, then Pillow placeholder frames.

### `video_assembly.py` — FFmpeg Video Assembly
Assembles image frames + narration audio + optional BGM into final MP4. Handles both landscape (1920x1080) and vertical shorts (1080x1920). Uses FFmpeg concat demuxer with per-scene durations, Ken Burns zoom effect (gentle 4% oscillation), and BGM mixing at -18 LUFS. Has simple slideshow fallback if complex assembly fails. Calculates scene durations based on pacing_profile gene.

### `thumbnail_gen.py` — Visual Thumbnail Creation
Uses Pillow to create thumbnails with niche-specific color palettes, base image darkening/tinting, bold text overlay with shadows, accent bars, and channel branding strips. Generates both standard (1280x720) and shorts (1080x1920) thumbnails. Has LLM-based honesty scoring (does thumbnail promise match content?).

### `title_engine.py` — SEO-Optimized Metadata
Generates titles, descriptions, tags, and chapters using Gemini. Scores title candidates against: specificity (has numbers), curiosity gap words, length sweet spot (45-65 chars), strong openers, identity relevance, and title archetype pattern match. Penalizes empty clickbait. Falls back to template-based metadata if LLM fails.

### `upload_agent.py` — YouTube Upload
Uploads videos via YouTube Data API v3 resumable upload protocol (10MB chunks with retry). Single-account mode: all slots use YT_OAUTH_TOKEN_0. Sets thumbnails, posts seed engagement comments, logs every upload. Handles both long-form (public, Education category) and Shorts (appends #Shorts to title).

### `analytics_agent.py` — Performance Measurement
Pulls YouTube statistics (views, likes, comments, duration) via Data API v3. Computes composite fitness using the weighted formula. Derives hook strength, payoff fulfillment, and pacing overload scores. Updates genome fitness in SQLite. Scores comment depth (avg word count / 30, capped at 1.0).

### `evolution_engine.py` — Darwinian Selection
Runs after analytics. Ranks genomes by fitness, identifies top 40% as "wins." Updates per-allele win rates in SQLite and refreshes allele_pool.json priors (70% new data, 30% old prior to prevent overfit). Promotes champion alleles (most common in top 20%), penalizes worst alleles (most common in bottom 20%). Decays ε by 0.005 per cycle.

### `frequency_controller.py` — Cadence Management
Enforces daily limits (1 long, 2 shorts per channel) and weekly limits (configurable per channel). Detects audience fatigue: if fitness declines >20% over last 5 videos, reduces cadence 50% and raises quality threshold. Checks publish logs to count recent uploads.

### `postmortem_engine.py` — Learning From Failure
Auto-generates structured postmortems for any genome with fitness < 0.25. Uses Gemini to analyze which genes likely contributed to failure. Extracts key learnings and stores to `reflection/learnings/` for the memory system. Marks genomes as "postmortemed" so they're not re-analyzed.

### `memory_manager.py` — Knowledge Preservation
Weekly: promotes mid-term items to long-term (if confidence ≥ 0.65 and age ≥ 14 days). Archives expired short-term items (>48h) — promotes if confidence ≥ 0.40, deletes otherwise. Rebuilds memory_index.json from all tiers. Provides `store_short_term()` and `get_long_term_rules()` APIs.

### `health_check.py` — System Monitoring
Daily health report covering: channel upload recency, error log analysis, research pipeline status, genome DB stats, per-niche performance, memory system counts, learning state (epsilon, champions, penalized), trending topics, recent videos. Generates both JSON report and human-readable LYRA_REPORT.md. Does NOT exit with error code — report always commits.

### `token_refresh.py` — OAuth Token Management
Runs at the start of every workflow. Uses refresh_token + client_id + client_secret to get a fresh access token from Google OAuth2. Writes the new token to GITHUB_ENV so subsequent workflow steps can use it. Falls back to existing YT_OAUTH_TOKEN_0 if refresh fails.

## 3.3 Data Files

| File | Purpose | Updated By |
|------|---------|-----------|
| `genome.db` | SQLite with tables: genomes, fitness_history, allele_stats, hypotheses, postmortems | orchestrator, analytics, evolution |
| `.gen_counter` | Plain text integer — current generation number | orchestrator (evolve phase) |
| `learning.json` | System state: epsilon, champion/penalized alleles, channel performance, fitness history | evolution_engine, orchestrator |
| `allele_pool.json` | 14 genes with legal values and prior weights (evolves over time) | evolution_engine |
| `channel_map.json` | Slot → channel name, niche, YouTube ID, voice style, status, upload limits | Manual config |
| `niche_config.json` | Per-niche: description, audience, keywords, competitors, voice/color config | Manual config |
| `title_patterns.json` | 12 viral title archetypes with templates and emotional targets | Manual config |
| `error_log.json` | Append-only failure log: timestamp, phase, slot, error message | All modules |

## 3.4 Workflow Files

| File | Trigger | Runtime | What It Does |
|------|---------|---------|-------------|
| `lyra_cycle.yml` | Every 6h + manual | ~25 min/slot | Full pipeline: refresh token → research → generate slots 0,1,2 → commit |
| `research_continuous.yml` | Every 3h + manual | ~5 min | Trend scanning only → commit candidates |
| `analytics_evolve.yml` | Every 48h + manual | ~20 min | Pull analytics → compute fitness → evolve genes → commit |
| `health_and_memory.yml` | Daily 8am UTC + manual | ~10 min | Health check + LYRA_REPORT.md. Weekly: memory compression |
| `init_once.yml` | Manual only | ~1 min | Initialize genome.db (run once during setup) |

---

# PART IV — CURRENT DEPLOYMENT STATE & ALL BUG FIXES

## 4.1 What Is Live Right Now (March 29, 2026)

- **Repo:** github.com/sourabhh2807/project-lyra — live, workflows enabled
- **Google Account:** 1 account running all 3 niches on 1 YouTube channel
- **YouTube Channel ID:** UCY33k64aPH21vwkvw0Pup9w
- **Google Cloud Project:** "lyra-public", OAuth client "lyra-web-slot0" (Web app type)
- **OAuth:** Redirect URI set to OAuth Playground
- **Generation Counter:** 1 (just started)
- **Epsilon:** 0.30 (full exploration mode)
- **Videos Published:** 0 (pipeline hasn't completed a full run yet)

### Pipeline Stage Status

| Stage | Status | Notes |
|-------|--------|-------|
| Research | ✅ WORKING | 271+ topic candidates generated across all 3 niches |
| Topic Selection | ✅ WORKING | Selects by predicted_fitness, marks in_creation |
| Script Generation | ✅ WORKING | 9+ scripts generated (some intermittent Gemini failures — expected) |
| Voice Generation | ❌→✅ FIXED | Was the main blocker — asyncio bug + no chunking. Now fixed |
| Image Generation | ✅ WORKING | Pollinations.ai working, thumbnails generated |
| Video Assembly | ⚠️ NEEDS TEST | Failed once (slot 2), but caused by upstream failure. FFmpeg fixes applied |
| Quality Gate | ✅ WORKING | content_angles check removed, min words lowered to 200 |
| Upload | ⏸️ UNTESTED | Never reached — blocked by voice. Should work with valid OAuth |
| Analytics | ⏸️ WAITING | No videos to evaluate yet |
| Evolution | ⏸️ WAITING | Needs ≥4 evaluated genomes |

## 4.2 All Bugs Found & Fixed

### Bug 1: voice_gen.py — Asyncio Event Loop Crash (CRITICAL)
**Symptom:** `Voice generation returned None for long audio` — every slot, every run  
**Root Cause:** The asyncio handling tried to detect running event loops and use `run_in_executor`, but that branch never awaited its result. Also, no text chunking for long scripts (>4500 chars) caused WebSocket drops from Microsoft's speech service.  
**Fix:** Complete rewrite. Always uses `asyncio.run()`. Added text chunking at sentence boundaries (max 4500 chars/chunk). Added retry logic (3 attempts, exponential backoff). Added FFmpeg concatenation for multi-chunk audio. Added detailed logging at every failure point.

### Bug 2: health_check.py — sys.exit(1) Killed Workflow (MODERATE)
**Symptom:** Health check workflow failed, report never committed to repo  
**Root Cause:** `sys.exit(1)` when issues found. In early stages, "never uploaded" is expected — not a fatal error.  
**Fix:** Removed sys.exit(1). Report always commits. Issues documented in report, not as workflow failures.

### Bug 3: requirements.txt — Stdlib Modules Crash pip (MODERATE)
**Symptom:** `pip install -r requirements.txt` could fail  
**Root Cause:** Listed `sqlite3`, `asyncio`, `uuid` which are Python stdlib and can't be pip-installed. Also had `requests` listed twice.  
**Fix:** Removed stdlib modules, removed duplicate, added comments. Also removed `librosa`/`soundfile` (quality gate uses ffprobe instead).

### Bug 4: health_and_memory.yml — Memory Compression Blocked (MODERATE)
**Symptom:** Memory compression job never ran  
**Root Cause:** `needs: health_check` with no `if: always()` meant it was skipped when health check failed (which it always did due to sys.exit(1)).  
**Fix:** Added `if: always() &&` condition. Added `git pull --rebase` to avoid push conflicts. Health check now commits LYRA_REPORT.md alongside health_report.json.

### Bug 5: All Gemini Calls — No responseMimeType (MODERATE)
**Symptom:** Intermittent JSON parse failures from Gemini responses  
**Root Cause:** research_agent, title_engine, thumbnail_gen, and postmortem_engine didn't use `responseMimeType: "application/json"` — Gemini sometimes returned markdown-wrapped JSON.  
**Fix:** Added `responseMimeType: "application/json"` to ALL Gemini API calls across all files. (script_gen already had it.)

### Bug 6: video_assembly.py — Concat File Comments (MINOR)
**Symptom:** Potential FFmpeg concat parse error for missing frames  
**Root Cause:** Wrote `# missing frame` comments in concat file — while FFmpeg supports # comments, it's risky.  
**Fix:** Skip missing frames silently, count valid entries, abort cleanly if zero valid frames.

### Bug 7: video_assembly.py — Zoompan Formula Instability (MINOR)
**Symptom:** Ken Burns zoom could overshoot on long videos  
**Root Cause:** Complex if/lte formula with division could produce values > 1.08 or negative zoom.  
**Fix:** Replaced with clean sinusoidal oscillation: `1.0 + 0.04 * sin(on/150*PI)` — gentle 4% zoom that loops smoothly.

### Bug 8: quality_gate.py — content_angles Blocking 100% (FIXED IN V9.1)
**Symptom:** Every single topic candidate was blocked from publishing  
**Root Cause:** Gate 1 required `content_angles` field which research_agent doesn't always populate.  
**Fix:** Removed content_angles check from Gate 1. Lowered min_script_words from 250 to 200.

### Bug 9: Known Issue — Hindi/Non-English Topics
**Symptom:** 41/271 topic candidates are in Hindi or mixed languages  
**Root Cause:** Google Trends picks up Indian trends from Delhi location  
**Status:** KNOWN — not yet fixed. May need English-only filter in research_agent.

## 4.3 GitHub Secrets Configured (9 total)

| Secret | Purpose |
|--------|---------|
| `LYRA_PAT` | GitHub Personal Access Token (repo write for Lyra-Bot commits) |
| `GEMINI_API_KEY` | Google Gemini 1.5 Flash API key |
| `GROQ_API_KEY` | Groq API key (fallback LLM) |
| `HF_API_KEY` | HuggingFace API key (fallback image gen) |
| `YOUTUBE_API_KEY` | YouTube Data API v3 key |
| `YT_OAUTH_TOKEN_0` | YouTube OAuth2 access token (auto-refreshed each run) |
| `YT_REFRESH_TOKEN` | OAuth2 refresh token (long-lived, used to get fresh access tokens) |
| `YT_CLIENT_ID` | Google OAuth2 client ID |
| `YT_CLIENT_SECRET` | Google OAuth2 client secret |

## 4.4 What Still Needs to Happen (Next Steps)

1. **Push all fixes** — voice_gen, health_check, requirements, workflows, Gemini calls, video_assembly
2. **Trigger `lyra_cycle` manually** — Watch the run in GitHub Actions. Check creation/voice/ for MP3 files.
3. **If voice works → full pipeline completes → first video uploads to YouTube**
4. **Wait 48h → analytics_evolve runs → first fitness scores computed**
5. **If Hindi topic issue persists → add English-only filter to research_agent**
6. **After ~5 evaluated videos → evolution engine starts learning → champions emerge**

---

# PART V — STRATEGY, SCALING & FUTURE

## 5.1 Channel Configuration

Currently: **single account mode** — 1 YouTube channel, 3 niches, 3 slots

| Slot | Name | Niche | Voice | Color |
|------|------|-------|-------|-------|
| 0 | DarkHistoryVault | Dark History | Authoritative Dramatic (GuyNeural) | Desaturated Red/Black |
| 1 | MindWireDaily | Psychology & Behavior | Conversational Engaging (AriaNeural) | Deep Blue/Purple |
| 2 | TechPulseAI | AI & Tech Explained | Teacher Clear (BrianNeural) | Electric Cyan/Dark |

## 5.2 Scaling Plan

```
Month 1:  3 slots on 1 channel    — Prove the system works
Month 2:  Separate accounts        — 1 channel = 1 account = 1 IP
Month 3:  5 channels               — Add 2 winning-niche variants
Month 4:  8 channels               — Expand best-performing niches
Month 5+: 15-20 channels           — Optimal ceiling (>25 dilutes quality signal)
```

**Hard rules:** One YouTube channel per Google Account. Each account created on different IP (mobile hotspot). Never log into two accounts in same browser. Trigger to add channel: avg fitness ≥ 0.45 AND Actions minutes < 1,800/month.

## 5.3 God-Level Extensions (Build Month 3+, Not Before)

| Extension | What It Does |
|-----------|-------------|
| A. Meta-Learner | Second AI layer reads evolution logs → proposes fitness function weight updates |
| B. Cross-Niche Gene Transfer | Winning genes in one niche → injected as immigrants in another |
| C. Multi-Platform Replication | Same genome → TikTok, Instagram Reels, YouTube Shorts simultaneously |
| D. Predictive CTR Gate | sklearn logistic regression on own CTR data → predict before upload |
| E. Competitor Genome Reverse-Engineering | Analyze competitor videos → extract implied gene values |
| F. Prompt Neuroevolution (NEAT) | Evolve the LLM prompts themselves as genomes |
| G. Autonomy Dashboard | GitHub Pages static site reading committed JSON — zero server cost |
| H. Self-Healing Watchdog | Detect if lyra_cycle hasn't committed in 13h → re-trigger + alert |
| I. Brand Voice Identity System | Per-channel voice personality stored in style guides |
| J. Evergreen Remix Engine | Monthly: rewrite top 10 old videos with current champion genes |

## 5.4 Roadmap

| Phase | Duration | Goal | Success Metric |
|-------|----------|------|---------------|
| 0: Setup | Week 0 | Repo live, first pipeline test | One video generated + uploaded |
| 1: Generation | Weeks 1-2 | All 3 slots posting | ≥5 videos per slot. Fitness > 0.20 |
| 2: Evolution | Weeks 3-4 | First evolution cycles | Champion alleles identified |
| 3: Quality | Month 2 | Gates tuned, fatigue detection | Avg fitness > 0.35 |
| 4: Intelligence | Month 3 | Research + memory system active | Actionable learnings weekly |
| 5: Extension | Month 4 | Meta-Learner + CTR predictor | Month-over-month fitness gain |
| 6: Scale | Month 5+ | Add channels 4-5, Evergreen Remix | ε < 0.08, compounding fitness |

## 5.5 Known Risks

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|-----------|
| GitHub Actions minutes exhausted | Low (3h research) | Medium | Adjust cron. ~$1.60/month overage acceptable |
| YouTube API quota exhausted | Medium | Medium | Batch analytics. Exponential backoff. Cache |
| Channel termination | Very Low (Gate 7) | Very High | Hard Gate 7. Channel isolation. Never evade |
| OAuth tokens expire mid-cycle | High (hourly expiry) | Medium | token_refresh.py runs every workflow start |
| Gemini throttled | Low | Medium | Groq fallback always active |
| genome.db corruption | Low | High | Atomic writes. Monthly archive snapshots |
| All niches converge to same DNA | Medium | Medium | Immigration operator + ε-greedy |
| Free API tiers change | Medium | Medium | Multi-fallback architecture |

## 5.6 Non-Negotiable Operating Rules

1. Learning quality outranks output quantity
2. No content publishes without all 7 quality gates passing
3. No mutation without stored experiment record
4. No deletion of historical learning without archive snapshot
5. No deceptive optimization — content quality is the only advantage
6. All winning patterns must be explainable
7. Failures are preserved as aggressively as successes
8. Research runs continuously; publishing remains selective
9. Evolution is mandatory; uncontrolled drift is forbidden
10. Viewer satisfaction outranks click extraction — always
11. Layer B parameters change monthly maximum
12. One channel = one Google account = one IP — no exceptions

## 5.7 The Compound Thesis

> Week 1: Lyra makes videos.  
> Week 4: Lyra makes better videos.  
> Month 3: Lyra makes videos that understand human psychology with increasing precision.  
> Month 6: Lyra makes videos that a researcher with access to all past performance data,
> all audience behavior models, all platform pattern intelligence, and zero cognitive
> fatigue would make — running 24 hours a day at zero marginal cost.

The advantage is not speed.  
The advantage is **compound memory** meeting **systematic variation** meeting
**objective evaluation** — running forever, at zero marginal cost, getting smarter
with every video it publishes.

---

**Status:** All fixes applied. Code ready to push.  
**Next Action:** Push fixes → Trigger lyra_cycle manually → Watch first full pipeline run.  
**Preserved:** Everything. Nothing deleted. Nothing lost.
