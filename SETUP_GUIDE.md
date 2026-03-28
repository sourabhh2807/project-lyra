# 🚀 PROJECT LYRA — COMPLETE SETUP GUIDE
### From Zero to Fully Autonomous in One Session

**Version:** 9.0 | **Channels:** Start with 3 | **Cost:** $0/month

---

## ⚠️ READ THIS FIRST — ACCOUNT STRATEGY

The single most important rule before you touch anything:

> **One YouTube channel = One Google Account = One IP address at creation.**

Your 50-channels-on-one-Google-account setup is the most dangerous possible configuration.
If that account gets banned, all 50 channels die simultaneously.

**The correct strategy:**
- 3 channels now (this guide)
- Each on its own Google account
- Each Google account created from a different network connection
- Mobile hotspot is the easiest way to switch IPs between account creations

---

## WHAT YOU NEED BEFORE STARTING

- [ ] A computer with Python 3.11+ installed
- [ ] A GitHub account
- [ ] 3 separate Google accounts (each created on different IP)
- [ ] 3 YouTube channels (one per Google account)
- [ ] 1 Google Cloud project per channel (for API access)
- [ ] Free accounts: Gemini API, Groq API, HuggingFace

**Time required:** 2–3 hours for full setup.

---

## PHASE 0: LOCAL MACHINE SETUP (30 minutes)

### Step 1 — Clone / Create the Repository

```bash
# Option A: Create new GitHub repo named "project-lyra"
# Then clone it locally
git clone https://github.com/YOUR_USERNAME/project-lyra.git
cd project-lyra
```

### Step 2 — Upload All Project Files

Upload every file from this project into the repository maintaining the exact folder structure:

```
project-lyra/
├── .github/workflows/
│   ├── lyra_cycle.yml
│   ├── analytics_evolve.yml
│   ├── research_continuous.yml
│   └── health_and_memory.yml
├── src/
│   ├── orchestrator.py
│   ├── research_agent.py
│   ├── topic_selector.py
│   ├── script_gen.py
│   ├── voice_gen.py
│   ├── asset_gen.py
│   ├── video_assembly.py
│   ├── thumbnail_gen.py
│   ├── title_engine.py
│   ├── upload_agent.py
│   ├── analytics_agent.py
│   ├── evolution_engine.py
│   ├── frequency_controller.py
│   ├── postmortem_engine.py
│   ├── memory_manager.py
│   └── health_check.py
├── data/
│   ├── channel_map.json
│   ├── niche_config.json
│   ├── allele_pool.json
│   ├── learning.json
│   ├── title_patterns.json
│   └── error_log.json
├── governance/
│   └── thresholds.json
├── [all empty folders with .gitkeep]
├── init_db.py
├── get_oauth_token.py
├── refresh_token.py
├── requirements.txt
└── .gitignore
```

### Step 3 — Create Empty Folder Placeholders

GitHub doesn't track empty folders. Create `.gitkeep` files:

```bash
# Run this from inside your project-lyra folder
for dir in \
  memory/short_term memory/mid_term memory/long_term memory/evergreen \
  research/raw/trends research/raw/competitors research/raw/comments \
  research/processed/topic_candidates research/processed/audience_maps \
  research/processed/saturation_maps \
  reflection/postmortems reflection/learnings \
  reflection/failed_hypotheses reflection/promoted_hypotheses \
  experiments/queued experiments/running experiments/concluded \
  analytics/raw_exports analytics/normalized analytics/retention \
  archive/snapshots creation/briefs creation/scripts \
  creation/voice creation/visuals creation/packaging \
  execution/publish_logs execution/render; do
  mkdir -p "$dir"
  touch "$dir/.gitkeep"
done
```

### Step 4 — Install Dependencies Locally

```bash
pip install requests python-dotenv google-generativeai \
  google-auth google-auth-oauthlib google-auth-httplib2 \
  google-api-python-client pytrends edge-tts \
  Pillow librosa soundfile numpy
```

---

## PHASE 1: API KEYS SETUP (30 minutes)

### Step 5 — Get Your Free API Keys

#### A. Gemini API Key (Primary LLM — Free)
1. Go to https://aistudio.google.com/app/apikey
2. Click **Create API Key**
3. Copy the key → save as `GEMINI_API_KEY`
4. Free tier: 15 requests/minute, 1M tokens/day — sufficient for Lyra

#### B. Groq API Key (Fallback LLM — Free)
1. Go to https://console.groq.com
2. Sign up → API Keys → Create
3. Copy the key → save as `GROQ_API_KEY`
4. Free tier: 14,400 requests/day — only used as Gemini fallback

#### C. HuggingFace API Key (Image generation fallback — Free)
1. Go to https://huggingface.co/settings/tokens
2. New Token → Read access
3. Copy → save as `HF_API_KEY`
4. Free tier: 1,000 inference calls/day

#### D. YouTube Data API Key (Analytics — Free)
This is a PUBLIC API key (not OAuth). Used for reading trending data.
1. Go to console.cloud.google.com
2. Create a project (or use existing)
3. Enable **YouTube Data API v3**
4. Credentials → Create API Key
5. Copy → save as `YOUTUBE_API_KEY`
6. Free tier: 10,000 units/day

---

## PHASE 2: YOUTUBE OAUTH SETUP (60 minutes — most critical phase)

**Do this for each channel separately. Each requires its own Google account.**

### Step 6 — Set Up Google Cloud for Channel 0 (Dark History Vault)

**⚠️ Use a VPN or mobile hotspot if you created this Google account on a different IP.**

1. Go to console.cloud.google.com
2. Sign in with **Channel 0's Google account** (not your personal account)
3. Create a new project: `lyra-channel-0`
4. In the left menu → **APIs & Services → Library**
5. Search for "YouTube Data API v3" → Enable it
6. Go to **APIs & Services → OAuth consent screen**
   - User type: **External**
   - App name: `Lyra Content System`
   - User support email: your email
   - Developer contact: your email
   - Click Save and Continue through all steps
   - **Add Test Users**: add the Channel 0 Google account email
7. Go to **APIs & Services → Credentials**
   - Click **Create Credentials → OAuth 2.0 Client IDs**
   - Application type: **Desktop app**
   - Name: `lyra-desktop-slot0`
   - Click Create
   - **Download JSON** → save as `client_secrets_slot0.json` in the project folder

**Repeat Steps 6 for Channel 1 (MindWire Daily) → save as `client_secrets_slot1.json`**
**Repeat Steps 6 for Channel 2 (TechPulse AI) → save as `client_secrets_slot2.json`**

### Step 7 — Get OAuth Access Tokens

Run this for each channel from your local machine:

```bash
# Channel 0
python get_oauth_token.py --slot 0
# A browser window will open. Sign in with Channel 0's Google account.
# Authorize the app.
# Copy the ACCESS TOKEN printed in the terminal.

# Channel 1
python get_oauth_token.py --slot 1

# Channel 2
python get_oauth_token.py --slot 2
```

**What you get:**
- An **access token** (valid ~1 hour) → goes into GitHub Secret
- A **refresh token** (valid until revoked) → save in `token_slotX.json` locally

**⚠️ NEVER commit `token_slotX.json` or `client_secrets_slotX.json` to GitHub.**
They are in `.gitignore` already, but double-check.

---

## PHASE 3: GITHUB REPOSITORY SETUP (20 minutes)

### Step 8 — Create GitHub Personal Access Token

1. GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Generate new token (classic)
3. Name: `LYRA_PAT`
4. Expiration: 90 days (or No expiration)
5. Scopes: check **repo** (full repo access)
6. Generate → copy the token

### Step 9 — Add All GitHub Secrets

Go to your GitHub repo → **Settings → Secrets and variables → Actions → New repository secret**

Add each of these:

| Secret Name | Value | Where to get it |
|---|---|---|
| `LYRA_PAT` | Your GitHub PAT | Step 8 above |
| `GEMINI_API_KEY` | Gemini API key | Step 5A |
| `GROQ_API_KEY` | Groq API key | Step 5B |
| `HF_API_KEY` | HuggingFace token | Step 5C |
| `YOUTUBE_API_KEY` | YouTube Data API key | Step 5D |
| `YT_OAUTH_TOKEN_0` | Access token from slot 0 | Step 7 |
| `YT_OAUTH_TOKEN_1` | Access token from slot 1 | Step 7 |
| `YT_OAUTH_TOKEN_2` | Access token from slot 2 | Step 7 |

### Step 10 — Update channel_map.json with Real Channel IDs

1. Go to each YouTube channel
2. Click the channel icon → **Your channel**
3. The URL will be: `youtube.com/channel/UCxxxxxxxxxxxxxxxxx`
4. Copy that ID (starts with UC...)
5. Open `data/channel_map.json` and replace:
   - `"REPLACE_WITH_CHANNEL_ID_0"` → your Channel 0 ID
   - `"REPLACE_WITH_CHANNEL_ID_1"` → your Channel 1 ID
   - `"REPLACE_WITH_CHANNEL_ID_2"` → your Channel 2 ID
6. Commit and push this change

### Step 11 — Initialize the Database

Run locally to create `genome.db`:

```bash
python init_db.py
```

You should see:
```
[INIT] genome.db created at data/genome.db
[INIT] Generation counter initialized at 0
[INIT] Memory index created
[INIT] Database initialization complete. System ready.
```

Commit `data/genome.db` to the repo:

```bash
git add data/genome.db data/.gen_counter memory/memory_index.json
git commit -m "init: database initialized"
git push
```

---

## PHASE 4: FIRST TEST RUN (20 minutes)

### Step 12 — Enable GitHub Actions

1. Go to your repo on GitHub
2. Click **Actions** tab
3. If you see "Workflows aren't being run on this repository", click **I understand my workflows, go ahead and enable them**

### Step 13 — Run First Manual Test

1. Go to **Actions** tab
2. Click **Lyra Research Continuous** in the left sidebar
3. Click **Run workflow** → **Run workflow**
4. Watch the logs in real-time

If it passes (green checkmark): research is working ✓

Then test content generation:
1. Click **Lyra Master Cycle** in the sidebar
2. Click **Run workflow** → **Run workflow**
3. Watch logs for slot 0

**First run will be slow** (~25-35 minutes) because:
- It installs all Python packages
- It generates scripts (LLM calls take time)
- It generates images (API calls)
- It synthesizes voice (CPU TTS)
- It assembles video (FFmpeg encoding)

### Step 14 — Verify the Upload

1. Go to Channel 0's YouTube Studio
2. You should see a new video in **Content** (may be processing)
3. If it's there → **SUCCESS. The system is live.**

---

## PHASE 5: ONGOING MAINTENANCE

### Token Renewal (Every ~55 days)

OAuth access tokens expire. Refresh them monthly:

```bash
# On your local machine
python refresh_token.py --slot 0
# Copy the new token → update GitHub Secret YT_OAUTH_TOKEN_0

python refresh_token.py --all   # Refresh all at once
```

Then update each `YT_OAUTH_TOKEN_X` secret in GitHub Settings.

### Monitoring

- **Daily**: Check Actions tab for any red (failed) workflow runs
- **Weekly**: Look at `reflection/learnings/` for what the system is learning
- **Monthly**: Review `MONTHLY_REPORT.md` (auto-generated after evolution runs)

### Adding a 4th Channel (Month 2+)

1. Create a new Google account on a different IP/device
2. Create a YouTube channel on it
3. Set up Google Cloud project → OAuth credentials (Steps 6-7)
4. Add new entry to `data/channel_map.json` with `"slot": 3`
5. Add `data/niche_config.json` entry for the new niche
6. Add `YT_OAUTH_TOKEN_3` GitHub Secret
7. Add `generate_slot_3` job to `lyra_cycle.yml` following the same pattern
8. Commit and push → system automatically picks up the new channel

---

## TROUBLESHOOTING

### ❌ "GEMINI_API_KEY not set"
→ Check GitHub Secrets. Secret name must match exactly (case-sensitive).

### ❌ "No OAuth token for slot X"
→ The access token has expired (they last ~1 hour from creation, but GitHub
  runs it immediately). Re-run `get_oauth_token.py --slot X` and update the secret.
  Note: After the first successful upload, you can use `refresh_token.py` for renewals.

### ❌ "FFmpeg: No such file or directory"
→ The `sudo apt-get install -y ffmpeg` step failed. Check the workflow logs.
  This is pre-installed on ubuntu-latest but the install command is a safety net.

### ❌ Video generated but not uploaded (upload_agent fails)
→ Most common cause: YouTube API quota exceeded (10,000 units/day).
  An upload costs ~1,600 units. So you can upload ~6 videos per day per API key.
  For 3 channels each uploading 1 long + 1 short = 6 uploads = right at the limit.
  Solution: Space out uploads. The frequency controller handles this automatically.

### ❌ "research/processed/topic_candidates/*.json — 0 files"
→ Research agent ran but produced no candidates. Check:
  - pytrends sometimes rate-limits. The fallback seed keywords will still generate candidates.
  - If Gemini quota is hit, the minimal candidate builder activates as fallback.

### ❌ Workflow times out after 45 minutes
→ Video assembly is slow on GitHub's free runners (CPU only).
  For long videos (10-15 min), assembly takes 3-5 minutes.
  Total pipeline: research(2m) + script(2m) + voice(3m) + images(5m) + assembly(5m) + upload(5m) = ~22 minutes.
  If hitting 45min limit, reduce `long_video_target_max` in channel_map.json to 8 minutes.

### ❌ Thumbnail looks bad / plain colored
→ The Pillow-based thumbnail generator needs fonts.
  Fonts are available on ubuntu-latest. If running locally, install:
  `sudo apt-get install fonts-dejavu-core`

---

## SYSTEM SCHEDULE REFERENCE

| Workflow | Frequency | What It Does |
|---|---|---|
| `lyra_cycle.yml` | Every 6 hours | Research → Generate → Upload for all 3 slots |
| `research_continuous.yml` | Every hour | Trend scanning only (lightweight) |
| `analytics_evolve.yml` | Every 48 hours | Pull YT analytics → evolve genome |
| `health_and_memory.yml` | Daily + Weekly | Health check + Memory tier promotions |

**Total GitHub Actions minutes/month estimate:**
- Master cycle: 4/day × 30days × 25min = ~3,000 min (across 3 parallel jobs = ~1,000 billed min)
- Research: 24/day × 30 × 3min = ~2,160 min billed
- Analytics: 15 × 20min = 300 min
- Health: 30 × 5min = 150 min
- **Total: ~3,610 minutes/month**

⚠️ **GitHub free tier is 2,000 minutes/month.**
This means you'll use your free tier plus need ~$1.61 extra (at $0.008/min for Linux runners).

**To stay within free tier:**
- Change research cron from hourly to every 3 hours: `'0 */3 * * *'`
- This reduces research minutes to ~720 min/month
- Total drops to ~2,170 min/month — just over free tier
- Or: Change master cycle from every 6h to every 8h: `'0 */8 * * *'`

**Recommendation:** The $1-2/month extra is worth it for a fully autonomous system.
Upgrade to GitHub Pro ($4/month) when any channel generates its first revenue.

---

## SUCCESS CHECKLIST

After completing all phases:

- [ ] Repository created with all files in correct structure
- [ ] `data/genome.db` initialized and committed
- [ ] 3 GitHub Secrets for API keys added
- [ ] 3 GitHub Secrets for OAuth tokens added (YT_OAUTH_TOKEN_0/1/2)
- [ ] `LYRA_PAT` secret added
- [ ] `channel_map.json` updated with real channel IDs
- [ ] First manual research workflow run succeeded (green)
- [ ] First manual master cycle run succeeded (green)
- [ ] Video visible in YouTube Studio for at least one channel

**When all boxes are checked, Project Lyra is LIVE.**
It will now run autonomously, posting videos, learning from performance,
and evolving its content strategy — 24 hours a day, 7 days a week.

---

*If any step fails, the error will appear in the GitHub Actions run logs.*
*Every error is also written to `data/error_log.json` in the repository.*
