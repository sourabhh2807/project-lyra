"""
upload_agent.py — Uploads videos to YouTube via Data API v3.
Uses per-channel OAuth tokens stored as GitHub Secrets.
Handles both long-form and Shorts uploads.
"""
import os, json, logging, time, random
import requests
from datetime import datetime, timezone

log = logging.getLogger("upload_agent")

YT_UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
YT_THUMB_URL  = "https://www.googleapis.com/youtube/v3/thumbnails/set"
YT_COMMENT_URL = "https://www.googleapis.com/youtube/v3/commentThreads"

class UploadAgent:
    def __init__(self, root):
        self.root = root

    def upload(self, video_path, thumbnail_path, title, description,
               tags, channel_slot, video_type="long"):
        """
        Upload video to YouTube. Returns video_id string or None.
        Requires YT_OAUTH_TOKEN_{slot} env var containing valid OAuth access token.
        """
        if not video_path or not os.path.exists(video_path):
            log.error(f"Video file not found: {video_path}")
            return None

        token = os.environ.get(f"YT_OAUTH_TOKEN_{channel_slot}", "")
        if not token:
            log.error(f"No OAuth token for slot {channel_slot} "
                      f"(set YT_OAUTH_TOKEN_{channel_slot} secret)")
            return None

        # Determine category and privacy
        category_id = "28"   # Science & Technology  (22=People, 24=Entertainment, 27=Education)
        privacy     = "public"

        # Shorts: title must contain #Shorts
        if video_type == "short" and "#Shorts" not in title:
            title = title[:90] + " #Shorts"

        body = {
            "snippet": {
                "title":       title[:100],
                "description": description[:4900],
                "tags":        tags[:500] if isinstance(tags, list) else [],
                "categoryId":  category_id,
                "defaultLanguage": "en",
            },
            "status": {
                "privacyStatus": privacy,
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

        # 1. Initiate resumable upload session
        init_url = (f"{YT_UPLOAD_URL}?uploadType=resumable"
                    f"&part=snippet,status")
        try:
            init_r = requests.post(init_url, headers=headers,
                                   json=body, timeout=30)
            if init_r.status_code not in (200, 201):
                log.error(f"Upload init failed {init_r.status_code}: {init_r.text[:300]}")
                return None

            upload_url = init_r.headers.get("Location", "")
            if not upload_url:
                log.error("No upload location returned")
                return None

            # 2. Upload file in chunks
            video_id = self._upload_chunks(upload_url, video_path, token)

            if not video_id:
                log.error("Chunk upload failed — no video_id returned")
                return None

            log.info(f"  Uploaded video_id={video_id}")

            # 3. Set thumbnail
            if thumbnail_path and os.path.exists(thumbnail_path):
                self._set_thumbnail(video_id, thumbnail_path, token)

            # 4. Seed pinned comment
            self._seed_comment(video_id, token, title)

            # 5. Log to publish log
            self._log_upload(channel_slot, video_id, video_type, title)

            return video_id

        except Exception as e:
            log.error(f"Upload crashed: {e}")
            return None

    def _upload_chunks(self, upload_url, video_path, token,
                       chunk_size=10 * 1024 * 1024):
        """Upload video in 10MB chunks with retry logic."""
        file_size = os.path.getsize(video_path)
        headers   = {"Authorization": f"Bearer {token}"}

        with open(video_path, "rb") as f:
            offset = 0
            retries = 0
            while offset < file_size:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                end = offset + len(chunk) - 1
                chunk_headers = {
                    **headers,
                    "Content-Range": f"bytes {offset}-{end}/{file_size}",
                    "Content-Type":  "video/mp4",
                }
                try:
                    r = requests.put(upload_url, data=chunk,
                                     headers=chunk_headers, timeout=120)
                    if r.status_code in (200, 201):
                        data = r.json()
                        return data.get("id", "")
                    elif r.status_code == 308:          # Resume incomplete
                        offset += len(chunk)
                        retries = 0
                        pct = int(offset / file_size * 100)
                        if pct % 20 == 0:
                            log.info(f"    Upload progress: {pct}%")
                    else:
                        retries += 1
                        if retries > 3:
                            log.error(f"Upload failed after 3 retries: {r.status_code}")
                            return None
                        time.sleep(5 * retries)
                except Exception as e:
                    retries += 1
                    log.warning(f"Chunk upload error (retry {retries}): {e}")
                    if retries > 3:
                        return None
                    time.sleep(10)
        return None

    def _set_thumbnail(self, video_id, thumbnail_path, token):
        try:
            with open(thumbnail_path, "rb") as f:
                img_data = f.read()
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type":  "image/jpeg",
            }
            r = requests.post(f"{YT_THUMB_URL}?videoId={video_id}",
                              data=img_data, headers=headers, timeout=30)
            if r.status_code in (200, 201):
                log.info("  Thumbnail set ✓")
            else:
                log.warning(f"Thumbnail set failed: {r.status_code}")
        except Exception as e:
            log.warning(f"Thumbnail upload error: {e}")

    def _seed_comment(self, video_id, token, title):
        """Post a seed comment as channel owner to prime engagement."""
        try:
            seeds = [
                "What part surprised you most? Drop it below 👇",
                "Which fact hit different? Let me know in the comments.",
                "Save this for later — there's a lot to unpack here.",
                "What should we cover next? Comment your topic 🔽",
            ]
            comment = random.choice(seeds)
            body = {
                "snippet": {
                    "videoId": video_id,
                    "topLevelComment": {
                        "snippet": {"textOriginal": comment}
                    }
                }
            }
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type":  "application/json",
            }
            r = requests.post(f"{YT_COMMENT_URL}?part=snippet",
                              json=body, headers=headers, timeout=15)
            if r.status_code in (200, 201):
                log.info("  Seed comment posted ✓")
        except Exception as e:
            log.warning(f"Seed comment failed: {e}")

    def _log_upload(self, slot, video_id, video_type, title):
        log_path = os.path.join(self.root, "execution/publish_logs",
                                f"upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                                f"_slot{slot}_{video_type}.json")
        with open(log_path, "w") as f:
            json.dump({
                "ts": datetime.now(timezone.utc).isoformat(),
                "slot": slot, "video_id": video_id,
                "video_type": video_type, "title": title,
            }, f, indent=2)
