"""
thumbnail_gen.py — Creates YouTube thumbnails using Pillow.
Generates long-video (1280x720) and shorts (1080x1920) thumbnails.
Applies niche color grade, bold text overlay, LLM honesty check.
"""
import os, json, requests, logging
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from datetime import datetime

log = logging.getLogger("thumbnail_gen")

# Niche color palettes: (background_tint, text_color, accent_color)
NICHE_PALETTES = {
    "dark_history":     ((15, 5, 5),    (255, 220, 200), (180, 30, 30)),
    "psychology_hacks": ((5, 10, 30),   (200, 220, 255), (60, 80, 200)),
    "ai_explained":     ((5, 20, 25),   (180, 255, 255), (0, 200, 220)),
    "default":          ((10, 10, 20),  (255, 255, 255), (200, 50, 50)),
}

class ThumbnailGenerator:
    def __init__(self, root):
        self.root   = root
        self.gemini = os.environ.get("GEMINI_API_KEY", "")
        self.font_dir = "/usr/share/fonts/truetype"

    # ── public ──────────────────────────────────────────────────────────────

    def create(self, base_image_path, overlay_text, slot, niche):
        """Create 1280x720 thumbnail. Returns path."""
        out_dir = os.path.join(self.root, "creation/packaging")
        os.makedirs(out_dir, exist_ok=True)
        ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = os.path.join(out_dir, f"thumb_{ts}_slot{slot}.jpg")
        self._render(base_image_path, overlay_text, niche, out, 1280, 720)
        return out

    def create_shorts(self, base_image_path, overlay_text, slot, niche):
        """Create 1080x1920 shorts thumbnail. Returns path."""
        out_dir = os.path.join(self.root, "creation/packaging")
        os.makedirs(out_dir, exist_ok=True)
        ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = os.path.join(out_dir, f"thumb_shorts_{ts}_slot{slot}.jpg")
        self._render(base_image_path, overlay_text, niche, out, 1080, 1920)
        return out

    def honesty_score(self, title, thumbnail_text, script_excerpt):
        """LLM-based check: does thumbnail/title promise match script content? Returns 0-1."""
        if not self.gemini:
            return 0.75  # default pass if no key
        prompt = f"""Rate how honestly this YouTube thumbnail/title represents the actual video content.

Title: {title}
Thumbnail text: {thumbnail_text}
Script excerpt (first 300 chars): {script_excerpt[:300]}

Score from 0.0 (completely misleading clickbait) to 1.0 (perfectly honest representation).
Return ONLY a JSON object: {{"score": 0.0, "reason": "brief explanation"}}"""
        try:
            resp = self._call_gemini(prompt)
            data = json.loads(resp)
            return float(data.get("score", 0.75))
        except Exception:
            return 0.75

    # ── rendering ────────────────────────────────────────────────────────────

    def _render(self, base_path, text, niche, out_path, W, H):
        palette = NICHE_PALETTES.get(niche, NICHE_PALETTES["default"])
        bg_tint, text_color, accent = palette

        # Base image
        if base_path and os.path.exists(base_path):
            try:
                img = Image.open(base_path).convert("RGB").resize((W, H), Image.LANCZOS)
                # Darken and tint
                enhancer = ImageEnhance.Brightness(img)
                img = enhancer.enhance(0.55)
                tint = Image.new("RGB", (W, H), bg_tint)
                img = Image.blend(img, tint, alpha=0.35)
            except Exception:
                img = Image.new("RGB", (W, H), bg_tint)
        else:
            img = Image.new("RGB", (W, H), bg_tint)
            # Gradient overlay
            for y in range(H):
                alpha = int(40 * (1 - y / H))
                for x in range(0, W, 4):
                    px = img.getpixel((x, y))
                    img.putpixel((x, y), tuple(min(255, c + alpha) for c in px))

        draw = ImageDraw.Draw(img)

        # Draw accent bar at bottom
        bar_h = int(H * 0.08)
        draw.rectangle([(0, H - bar_h), (W, H)], fill=accent)

        # Main text
        clean_text = str(text).upper()[:40] if text else "WATCH THIS"
        font_size  = self._optimal_font_size(clean_text, W, H)
        font       = self._load_font(font_size)

        # Text shadow
        tx, ty = W // 2, int(H * 0.52)
        for dx, dy in [(-3, -3), (3, -3), (-3, 3), (3, 3), (0, 4)]:
            draw.text((tx + dx, ty + dy), clean_text, font=font,
                      fill=(0, 0, 0), anchor="mm")

        # Main text
        draw.text((tx, ty), clean_text, font=font, fill=text_color, anchor="mm")

        # Channel brand strip at top
        draw.rectangle([(0, 0), (W, int(H * 0.06))], fill=(0, 0, 0, 180))

        img.save(out_path, "JPEG", quality=92)
        log.info(f"Thumbnail saved: {out_path}")

    def _optimal_font_size(self, text, W, H):
        chars = len(text)
        if chars <= 15:   return int(H * 0.18)
        elif chars <= 25: return int(H * 0.14)
        elif chars <= 35: return int(H * 0.11)
        else:             return int(H * 0.09)

    def _load_font(self, size):
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/ubuntu/Ubuntu-Bold.ttf",
        ]
        for path in candidates:
            if os.path.exists(path):
                try:
                    return ImageFont.truetype(path, size)
                except Exception:
                    pass
        return ImageFont.load_default()

    def _call_gemini(self, prompt):
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"gemini-1.5-flash:generateContent?key={self.gemini}")
        body = {"contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"maxOutputTokens": 200, "temperature": 0.3,
                                     "responseMimeType": "application/json"}}
        r = requests.post(url, json=body, timeout=20)
        r.raise_for_status()
        text = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"): text = text[4:]
        return text.strip()
