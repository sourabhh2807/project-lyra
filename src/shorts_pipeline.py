"""
Lyra V10 — Shorts Machine
Searches Pexels for beautiful HD vertical videos, adds background music,
uploads as YouTube Shorts. 2x daily, zero manual work.

No voiceover. No text overlay. No AI generation. Just real HD footage + music.
"""
import os, sys, json, random, time, requests, subprocess, logging
from datetime import datetime, timezone
from urllib.parse import quote

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("lyra")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ═══════════════════════════════════════════════════════════════════════════════
# SEARCH QUERIES — rotated randomly each run
# ═══════════════════════════════════════════════════════════════════════════════
SEARCH_QUERIES = [
    # Fashion & Style
    "fashion model walking", "runway model", "woman fashion photoshoot",
    "stylish woman city", "model posing", "glamour photography",
    "woman elegant dress", "fashion portrait", "model studio shoot",
    # Lifestyle & Aesthetic
    "beautiful woman lifestyle", "aesthetic girl", "woman morning routine",
    "woman coffee shop", "girl travel", "woman sunset golden hour",
    "woman luxury lifestyle", "girl aesthetic vibes",
    # Fitness & Confidence
    "woman fitness workout", "girl yoga", "woman gym training",
    "woman running outdoor", "fit woman portrait",
    # Beach & Summer
    "woman beach sunset", "girl summer vibes", "woman pool",
    "tropical woman", "woman ocean waves",
    # Urban & Night
    "woman night city lights", "girl neon lights", "woman urban portrait",
    "woman rooftop city", "girl street style",
    # Nature & Outdoor
    "beautiful woman nature", "woman flower garden", "girl outdoor portrait",
    "woman forest", "woman mountain view",
    # Glamour & Beauty
    "woman beauty closeup", "girl hair flip", "woman makeup glamour",
    "woman mirror portrait", "beautiful eyes woman",
]

# Background music search terms for Pixabay
MUSIC_QUERIES = [
    "chill lofi beat", "aesthetic background music", "trendy instagram beat",
    "cinematic mood", "smooth rnb instrumental", "deep house minimal",
    "night vibes beat", "fashion runway music", "modern trap beat soft",
]

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG & STATE
# ═══════════════════════════════════════════════════════════════════════════════

def load_json(path, default=None):
    full = os.path.join(ROOT, path) if not os.path.isabs(path) else path
    try:
        with open(full) as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}

def save_json(path, data):
    full = os.path.join(ROOT, path) if not os.path.isabs(path) else path
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w") as f:
        json.dump(data, f, indent=2)

def load_history():
    return load_json("data/upload_history.json", [])

def save_history(history):
    # Keep last 500 entries
    save_json("data/upload_history.json", history[-500:])

def get_used_video_ids():
    """Get set of Pexels video IDs already used."""
    history = load_history()
    return {str(h.get("pexels_video_id", "")) for h in history}

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1: FIND A VIDEO ON PEXELS
# ═══════════════════════════════════════════════════════════════════════════════

def search_pexels_video(api_key):
    """Search Pexels for a vertical video clip. Returns video dict or None."""
    used_ids = get_used_video_ids()
    headers = {"Authorization": api_key}

    # Try multiple queries until we find an unused video
    queries = random.sample(SEARCH_QUERIES, min(8, len(SEARCH_QUERIES)))

    for query in queries:
        log.info(f"Searching Pexels: '{query}'")
        try:
            page = random.randint(1, 5)
            r = requests.get(
                "https://api.pexels.com/v1/videos/search",
                headers=headers,
                params={
                    "query": query,
                    "orientation": "portrait",
                    "per_page": 15,
                    "page": page,
                    "size": "medium",
                    "min_duration": 5,
                    "max_duration": 30,
                },
                timeout=15
            )
            if r.status_code != 200:
                log.warning(f"Pexels API {r.status_code}: {r.text[:200]}")
                time.sleep(2)
                continue

            data = r.json()
            videos = data.get("videos", [])
            if not videos:
                continue

            # Filter: unused, has HD file, portrait orientation
            for video in videos:
                vid_id = str(video.get("id", ""))
                if vid_id in used_ids:
                    continue

                # Find best portrait video file (720p+ HD)
                best_file = _pick_best_file(video.get("video_files", []))
                if not best_file:
                    continue

                log.info(f"Found: '{video.get('url', '')}' (id={vid_id}, "
                         f"{best_file.get('width')}x{best_file.get('height')})")
                return {
                    "pexels_video_id": vid_id,
                    "download_url": best_file["link"],
                    "width": best_file.get("width", 720),
                    "height": best_file.get("height", 1280),
                    "duration": video.get("duration", 10),
                    "query": query,
                    "pexels_url": video.get("url", ""),
                    "photographer": video.get("user", {}).get("name", "Pexels"),
                }

            time.sleep(1)  # Rate limit courtesy

        except Exception as e:
            log.warning(f"Search failed for '{query}': {e}")
            time.sleep(2)

    log.error("No suitable video found after all queries")
    return None


def _pick_best_file(video_files):
    """Pick the best portrait video file — prefer 720p-1080p HD."""
    portrait_files = []
    for f in video_files:
        w = f.get("width", 0)
        h = f.get("height", 0)
        if h > w and h >= 720 and f.get("link"):  # Portrait + at least 720p
            portrait_files.append(f)

    if not portrait_files:
        # Fallback: any file with a link
        portrait_files = [f for f in video_files if f.get("link")]

    if not portrait_files:
        return None

    # Prefer 720p-1080p range (good quality, not too large)
    portrait_files.sort(key=lambda f: abs(f.get("height", 0) - 1080))
    return portrait_files[0]

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2: DOWNLOAD THE VIDEO
# ═══════════════════════════════════════════════════════════════════════════════

def download_video(url, out_path):
    """Download video file from Pexels."""
    log.info(f"Downloading video...")
    try:
        r = requests.get(url, stream=True, timeout=60)
        r.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                f.write(chunk)
        size = os.path.getsize(out_path)
        log.info(f"Downloaded: {size / 1024 / 1024:.1f} MB")
        return size > 50000
    except Exception as e:
        log.error(f"Download failed: {e}")
        return False

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 3: GET BACKGROUND MUSIC
# ═══════════════════════════════════════════════════════════════════════════════

def get_background_music(work_dir):
    """Get a royalty-free background music track."""
    music_dir = os.path.join(ROOT, "data/music")
    os.makedirs(music_dir, exist_ok=True)

    # Check if we already have music files cached
    existing = [f for f in os.listdir(music_dir) if f.endswith(".mp3")]
    if existing:
        pick = random.choice(existing)
        path = os.path.join(music_dir, pick)
        log.info(f"Using cached music: {pick}")
        return path

    # Download a royalty-free track from Pixabay
    pixabay_key = os.environ.get("PIXABAY_API_KEY", "")
    if pixabay_key:
        music = _download_pixabay_music(pixabay_key, music_dir)
        if music:
            return music

    # Fallback: generate a simple tone with FFmpeg (better than no music)
    log.info("Generating simple background tone with FFmpeg...")
    tone_path = os.path.join(work_dir, "bg_music.mp3")
    try:
        # Generate a soft ambient drone — not amazing but works
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "lavfi", "-i",
            "sine=frequency=220:duration=15,volume=0.3",
            "-f", "lavfi", "-i",
            "sine=frequency=330:duration=15,volume=0.2",
            "-filter_complex", "[0][1]amix=inputs=2:duration=longest",
            "-t", "15",
            tone_path
        ], capture_output=True, timeout=15)
        if os.path.exists(tone_path) and os.path.getsize(tone_path) > 1000:
            return tone_path
    except Exception as e:
        log.warning(f"Tone generation failed: {e}")

    return None


def _download_pixabay_music(api_key, music_dir):
    """Download a track from Pixabay's audio API."""
    query = random.choice(MUSIC_QUERIES)
    try:
        r = requests.get(
            "https://pixabay.com/api/",
            params={
                "key": api_key,
                "q": query,
                "media_type": "music",
                "per_page": 5,
                "safesearch": "true",
            },
            timeout=15
        )
        if r.status_code != 200:
            return None

        hits = r.json().get("hits", [])
        if not hits:
            return None

        track = random.choice(hits)
        audio_url = track.get("audio", "") or track.get("previewURL", "")
        if not audio_url:
            return None

        fname = f"music_{track.get('id', 'unknown')}.mp3"
        out_path = os.path.join(music_dir, fname)

        dr = requests.get(audio_url, timeout=30)
        if dr.status_code == 200 and len(dr.content) > 10000:
            with open(out_path, "wb") as f:
                f.write(dr.content)
            log.info(f"Downloaded music: {fname}")
            return out_path
    except Exception as e:
        log.warning(f"Pixabay music failed: {e}")
    return None

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 4: ASSEMBLE SHORT (trim video + add music)
# ═══════════════════════════════════════════════════════════════════════════════

def assemble_short(video_path, music_path, out_path, target_duration=9):
    """Trim video to target duration, add background music, output 9:16 Short."""
    log.info(f"Assembling Short ({target_duration}s)...")

    # Get video duration
    vid_dur = _get_duration(video_path)
    if vid_dur <= 0:
        log.error("Cannot read video duration")
        return False

    # Pick a random start point if video is longer than target
    max_start = max(0, vid_dur - target_duration - 0.5)
    start = round(random.uniform(0, max_start), 1) if max_start > 0 else 0
    actual_dur = min(target_duration, vid_dur - start)

    if music_path and os.path.exists(music_path):
        # Video + background music
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start),
            "-i", video_path,
            "-i", music_path,
            "-t", str(actual_dur),
            "-filter_complex",
            # Scale to 1080x1920 (9:16), add music at moderate volume
            "[0:v]scale=1080:1920:force_original_aspect_ratio=decrease,"
            "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,fps=30[v];"
            "[1:a]volume=0.5,afade=t=out:st=" + str(actual_dur - 1.5) + ":d=1.5[a]",
            "-map", "[v]",
            "-map", "[a]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            "-movflags", "+faststart",
            out_path
        ]
    else:
        # Video only (no music available)
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start),
            "-i", video_path,
            "-t", str(actual_dur),
            "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,"
                   "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,fps=30",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-an",  # No audio if original has none and no music
            "-movflags", "+faststart",
            out_path
        ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            log.error(f"FFmpeg failed: {result.stderr[-500:]}")
            # Fallback: simplest possible trim
            return _simple_trim(video_path, out_path, start, actual_dur)

        if os.path.exists(out_path) and os.path.getsize(out_path) > 50000:
            size_mb = os.path.getsize(out_path) / 1024 / 1024
            out_dur = _get_duration(out_path)
            log.info(f"Short assembled: {size_mb:.1f} MB, {out_dur:.1f}s")
            return True
        else:
            log.error("Output file missing or too small")
            return False

    except subprocess.TimeoutExpired:
        log.error("FFmpeg timed out")
        return False
    except Exception as e:
        log.error(f"Assembly crashed: {e}")
        return False


def _simple_trim(video_path, out_path, start, duration):
    """Ultra-simple fallback: just trim, no filters."""
    try:
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start), "-i", video_path,
            "-t", str(duration),
            "-c", "copy",
            out_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return result.returncode == 0 and os.path.exists(out_path)
    except Exception:
        return False


def _get_duration(path):
    try:
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=noprint_wrappers=1:nokey=1", path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return float(result.stdout.strip())
    except Exception:
        return 0.0

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 5: GENERATE TITLE & TAGS
# ═══════════════════════════════════════════════════════════════════════════════

TITLE_TEMPLATES = [
    "She walks like the world is hers 🔥",
    "Main character energy ✨",
    "This look tho 😍",
    "Confidence level: 💯",
    "Beauty that stops traffic 🚦",
    "That golden hour glow ☀️",
    "Aesthetic vibes only 🌸",
    "When the fit hits right 👗",
    "Drop dead gorgeous 💫",
    "Not from this planet 🌙",
    "Serving looks 24/7 💅",
    "Who else felt this? 💭",
    "POV: You see her walk in ✨",
    "This is what confidence looks like 👑",
    "Natural beauty hits different 🌿",
    "When she knows she's that girl 💋",
    "Unbothered queen energy 👸",
    "Can't take your eyes off 👀",
    "Definition of elegance 🖤",
    "Style game strong 💪",
    "She didn't even try 🤷‍♀️",
    "This vibe is everything 🎵",
    "When the lighting hits perfect 📸",
    "That walk, that confidence 🔥",
    "Beauty in motion 🌊",
]

TAGS_POOL = [
    "shorts", "viral", "beautiful", "aesthetic", "model", "fashion",
    "beauty", "trending", "fyp", "explore", "vibes", "lifestyle",
    "gorgeous", "confidence", "style", "elegant", "stunning", "glam",
    "photooftheday", "beautifulgirls", "fashionmodel",
]


def generate_metadata(video_info):
    """Generate title, description, and tags for the Short."""
    title = random.choice(TITLE_TEMPLATES)

    tags = random.sample(TAGS_POOL, min(10, len(TAGS_POOL)))

    description = (
        f"{title}\n\n"
        f"#shorts #viral #beautiful #aesthetic #trending #fyp\n\n"
        f"📸 Video: Pexels ({video_info.get('photographer', 'Pexels')})\n"
        f"🎵 Music: Royalty Free"
    )

    return {
        "title": title[:100],
        "description": description[:4900],
        "tags": tags,
    }

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 6: UPLOAD TO YOUTUBE
# ═══════════════════════════════════════════════════════════════════════════════

YT_UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"

def upload_youtube(video_path, metadata, token):
    """Upload video as YouTube Short. Returns video_id or None."""
    if not token:
        log.error("No YouTube OAuth token")
        return None

    title = metadata["title"]
    if "#Shorts" not in title:
        title = title[:90] + " #Shorts"

    body = {
        "snippet": {
            "title": title,
            "description": metadata["description"],
            "tags": metadata["tags"],
            "categoryId": "22",  # People & Blogs
            "defaultLanguage": "en",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
            "madeForKids": False,
        }
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "X-Upload-Content-Type": "video/mp4",
        "X-Upload-Content-Length": str(os.path.getsize(video_path)),
        "Content-Type": "application/json; charset=UTF-8",
    }

    try:
        # Initiate resumable upload
        init_url = f"{YT_UPLOAD_URL}?uploadType=resumable&part=snippet,status"
        log.info(f"Uploading: {title[:50]}...")
        init_r = requests.post(init_url, headers=headers, json=body, timeout=30)

        if init_r.status_code not in (200, 201):
            log.error(f"Upload init failed {init_r.status_code}: {init_r.text[:300]}")
            return None

        upload_url = init_r.headers.get("Location", "")
        if not upload_url:
            log.error("No upload location")
            return None

        # Upload the file
        with open(video_path, "rb") as f:
            up_headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "video/mp4",
            }
            up_r = requests.put(upload_url, data=f, headers=up_headers, timeout=180)

        if up_r.status_code in (200, 201):
            video_id = up_r.json().get("id", "")
            log.info(f"✅ UPLOADED: https://youtube.com/shorts/{video_id}")
            return video_id
        else:
            log.error(f"Upload failed {up_r.status_code}: {up_r.text[:300]}")
            return None

    except Exception as e:
        log.error(f"Upload crashed: {e}")
        return None

# ═══════════════════════════════════════════════════════════════════════════════
# STEP 7: TOKEN REFRESH
# ═══════════════════════════════════════════════════════════════════════════════

def refresh_token():
    """Refresh YouTube OAuth token. Returns fresh token."""
    refresh_tok = os.environ.get("YT_REFRESH_TOKEN", "")
    client_id = os.environ.get("YT_CLIENT_ID", "")
    client_secret = os.environ.get("YT_CLIENT_SECRET", "")

    if not all([refresh_tok, client_id, client_secret]):
        log.info("No refresh credentials, using existing token")
        return os.environ.get("YT_OAUTH_TOKEN_0", "")

    try:
        r = requests.post("https://oauth2.googleapis.com/token", data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_tok,
            "grant_type": "refresh_token",
        }, timeout=15)

        if r.status_code == 200:
            token = r.json().get("access_token", "")
            if token:
                log.info("OAuth token refreshed ✓")
                # Write to GITHUB_ENV for subsequent steps
                gh_env = os.environ.get("GITHUB_ENV", "")
                if gh_env:
                    with open(gh_env, "a") as f:
                        f.write(f"YT_OAUTH_TOKEN_0={token}\n")
                return token
    except Exception as e:
        log.warning(f"Token refresh failed: {e}")

    return os.environ.get("YT_OAUTH_TOKEN_0", "")

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════

def run():
    """Run the complete Shorts pipeline once."""
    log.info("=" * 60)
    log.info("LYRA V10 — SHORTS MACHINE")
    log.info("=" * 60)

    # Check required env vars
    pexels_key = os.environ.get("PEXELS_API_KEY", "")
    if not pexels_key:
        log.error("PEXELS_API_KEY not set!")
        sys.exit(1)

    # Refresh YouTube token
    yt_token = refresh_token()
    if not yt_token:
        log.error("No YouTube token available!")
        sys.exit(1)

    # Create work directory
    work_dir = os.path.join(ROOT, "tmp")
    os.makedirs(work_dir, exist_ok=True)

    try:
        # Step 1: Find video
        video_info = search_pexels_video(pexels_key)
        if not video_info:
            log.error("FAILED: No video found")
            return False

        # Step 2: Download
        raw_path = os.path.join(work_dir, "raw_video.mp4")
        if not download_video(video_info["download_url"], raw_path):
            log.error("FAILED: Download failed")
            return False

        # Step 3: Get music
        music_path = get_background_music(work_dir)

        # Step 4: Assemble Short
        short_path = os.path.join(work_dir, "short_final.mp4")
        if not assemble_short(raw_path, music_path, short_path, target_duration=9):
            log.error("FAILED: Assembly failed")
            return False

        # Step 5: Generate metadata
        metadata = generate_metadata(video_info)

        # Step 6: Upload to YouTube
        video_id = upload_youtube(short_path, metadata, yt_token)

        if video_id:
            # Save to history
            history = load_history()
            history.append({
                "ts": datetime.now(timezone.utc).isoformat(),
                "pexels_video_id": video_info["pexels_video_id"],
                "youtube_video_id": video_id,
                "title": metadata["title"],
                "query": video_info["query"],
                "pexels_url": video_info["pexels_url"],
            })
            save_history(history)

            log.info("=" * 60)
            log.info(f"✅ SUCCESS: https://youtube.com/shorts/{video_id}")
            log.info("=" * 60)
            return True
        else:
            log.error("FAILED: Upload failed")
            return False

    finally:
        # Cleanup work directory
        import shutil
        try:
            shutil.rmtree(work_dir, ignore_errors=True)
        except Exception:
            pass


if __name__ == "__main__":
    run()
