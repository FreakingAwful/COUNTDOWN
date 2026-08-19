"""
Self-hosted countdown image generator for the ROG 20 Edition pre-order EDM.

Serves a PNG that shows DAYS / HOURS / MINS / SECS remaining until the
target datetime, recalculated fresh on every request. Because email clients
can't run JS, this is what makes an email "countdown" work at all: the
<img src="..."> in the email points at this endpoint, and every time a
recipient opens the email, their client re-requests the image and gets
back accurate numbers for that exact moment.

Requirements:
    pip install flask Pillow

Run:
    python countdown_generator.py
    -> GET http://localhost:5000/countdown/rog20.png

In production, put this behind your normal app server / CDN and point the
email's <img src> at the public URL, e.g.:
    https://your-domain.com/edm/countdown/rog20.png
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from io import BytesIO

from flask import Flask, send_file, request, make_response
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)

# ---- Configure your event here -------------------------------------------
TARGET_TZ = ZoneInfo("Asia/Manila")
TARGET_DATETIME = datetime(2026, 8, 25, 0, 0, 0, tzinfo=TARGET_TZ)

# ---- Visual styling (matches the ROG 20 Edition EDM dark theme) ----------
BG_COLOR = (20, 20, 23, 255)          # #141417 — matches the email section bg
DIGIT_COLOR = (255, 255, 255, 255)    # #FFFFFF
LABEL_COLOR = (138, 138, 143, 255)    # #8A8A8F
SEPARATOR_COLOR = (255, 27, 27, 255)  # #FF1B1B — ROG red
EXPIRED_COLOR = (255, 27, 27, 255)

IMG_WIDTH = 460
IMG_HEIGHT = 100

# Bundled DejaVu fonts ship with Pillow by default; swap these paths for
# your own brand font files (e.g. a Rajdhani .ttf) if you have them.
try:
    DIGIT_FONT = ImageFont.truetype("DejaVuSans-Bold.ttf", 40)
    LABEL_FONT = ImageFont.truetype("DejaVuSans-Bold.ttf", 11)
    SEP_FONT = ImageFont.truetype("DejaVuSans-Bold.ttf", 32)
except OSError:
    DIGIT_FONT = ImageFont.load_default()
    LABEL_FONT = ImageFont.load_default()
    SEP_FONT = ImageFont.load_default()


def render_countdown_png(target_dt: datetime) -> BytesIO:
    now = datetime.now(TARGET_TZ)
    remaining = target_dt - now

    img = Image.new("RGBA", (IMG_WIDTH, IMG_HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    if remaining.total_seconds() <= 0:
        text = "PRE-ORDERS ARE LIVE"
        bbox = draw.textbbox((0, 0), text, font=DIGIT_FONT)
        w = bbox[2] - bbox[0]
        draw.text(((IMG_WIDTH - w) / 2, (IMG_HEIGHT - 30) / 2), text,
                   font=DIGIT_FONT, fill=EXPIRED_COLOR)
        buf = BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf

    days = remaining.days
    hours, rem = divmod(remaining.seconds, 3600)
    minutes, seconds = divmod(rem, 60)

    units = [
        (f"{days:02d}", "DAYS"),
        (f"{hours:02d}", "HOURS"),
        (f"{minutes:02d}", "MINS"),
        (f"{seconds:02d}", "SECS"),
    ]

    # Layout: 4 number blocks with ":" separators, centered horizontally
    block_w = 90
    sep_w = 20
    total_w = block_w * 4 + sep_w * 3
    x = (IMG_WIDTH - total_w) / 2

    for i, (value, label) in enumerate(units):
        num_bbox = draw.textbbox((0, 0), value, font=DIGIT_FONT)
        num_w = num_bbox[2] - num_bbox[0]
        draw.text((x + (block_w - num_w) / 2, 10), value,
                   font=DIGIT_FONT, fill=DIGIT_COLOR)

        lbl_bbox = draw.textbbox((0, 0), label, font=LABEL_FONT)
        lbl_w = lbl_bbox[2] - lbl_bbox[0]
        draw.text((x + (block_w - lbl_w) / 2, 66), label,
                   font=LABEL_FONT, fill=LABEL_COLOR)

        x += block_w
        if i < 3:
            draw.text((x + (sep_w - 10) / 2, 14), ":",
                       font=SEP_FONT, fill=SEPARATOR_COLOR)
            x += sep_w

    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


@app.route("/edm/countdown/rog20.png")
def countdown_image():
    # Optional: allow an override via query param for testing,
    # e.g. /countdown/rog20.png?target=2026-08-25T00:00:00+08:00
    target_param = request.args.get("target")
    target_dt = TARGET_DATETIME
    if target_param:
        try:
            target_dt = datetime.fromisoformat(target_param)
        except ValueError:
            pass

    buf = render_countdown_png(target_dt)
    response = make_response(send_file(buf, mimetype="image/png"))
    # Critical: prevent email clients / proxies from caching a stale frame
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
