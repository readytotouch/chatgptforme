#!/usr/bin/env python3
"""Generate every raster image of the site from code: favicons, touch icons,
tile icons, favicon.ico, the Open Graph image and one OG image per AI assistant.

Run from the repository root:  python3 tools/images.py
Requires Pillow. The vector source of the icon is public/icon.svg; this script
redraws the same geometry with Pillow because no SVG rasteriser is assumed.
"""
import json
import os

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "public")
VIOLET = (124, 58, 237)   # #7c3aed
BLUE = (37, 99, 235)      # #2563eb
WHITE = (255, 255, 255)
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def font(size, bold=True):
    try:
        return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, size)
    except OSError:
        return ImageFont.load_default()


def gradient(w, h, c1=VIOLET, c2=BLUE):
    """Diagonal gradient from top-left (c1) to bottom-right (c2)."""
    img = Image.new("RGB", (w, h))
    px = img.load()
    span = float(w + h - 2) or 1.0
    for y in range(h):
        for x in range(w):
            t = (x + y) / span
            px[x, y] = tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))
    return img


def sparkle(cx, cy, outer, inner):
    return [
        (cx, cy - outer), (cx + inner, cy - inner), (cx + outer, cy),
        (cx + inner, cy + inner), (cx, cy + outer), (cx - inner, cy + inner),
        (cx - outer, cy), (cx - inner, cy - inner),
    ]


def draw_icon(size, corner=True):
    """The app icon at `size` px, rendered at 4x and downsampled for smooth edges."""
    s = 4
    n = 512 * s
    k = n / 512.0
    bg = gradient(256, 256).resize((n, n), Image.BILINEAR)
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    mask = Image.new("L", (n, n), 0)
    md = ImageDraw.Draw(mask)
    if corner:
        md.rounded_rectangle([0, 0, n - 1, n - 1], radius=int(112 * k), fill=255)
    else:
        md.rectangle([0, 0, n - 1, n - 1], fill=255)
    img.paste(bg, (0, 0), mask)

    d = ImageDraw.Draw(img)
    # speech bubble: rounded body + tail
    d.rounded_rectangle([88 * k, 120 * k, 424 * k, 368 * k], radius=int(64 * k), fill=WHITE)
    d.polygon([(150 * k, 306 * k), (232 * k, 368 * k), (150 * k, 430 * k)], fill=WHITE)
    # AI sparkles
    d.polygon(sparkle(256 * k, 244 * k, 88 * k, 26 * k), fill=VIOLET)
    d.polygon(sparkle(356 * k, 334 * k, 34 * k, 10 * k), fill=VIOLET)
    return img.resize((size, size), Image.LANCZOS)


def write_icons():
    sizes = {
        "android-icon-{0}x{0}.png": [36, 48, 72, 96, 144, 192],
        "apple-icon-{0}x{0}.png": [57, 60, 72, 76, 114, 120, 144, 152, 180],
        "favicon-{0}x{0}.png": [16, 32, 96],
        "ms-icon-{0}x{0}.png": [70, 144, 150, 310],
    }
    cache = {}

    def icon(sz):
        if sz not in cache:
            cache[sz] = draw_icon(sz)
        return cache[sz]

    for pattern, lst in sizes.items():
        for sz in lst:
            icon(sz).save(os.path.join(ROOT, pattern.format(sz)), optimize=True)
    icon(192).save(os.path.join(ROOT, "apple-icon.png"), optimize=True)
    icon(192).save(os.path.join(ROOT, "apple-icon-precomposed.png"), optimize=True)
    icon(48).save(os.path.join(ROOT, "favicon.ico"), sizes=[(16, 16), (32, 32), (48, 48)])
    print("icons written")


def chip(d, x, y, text, f, fill, color):
    """Rounded label; returns the x after it."""
    tw = d.textlength(text, font=f)
    pad_x, h = 18, 44
    d.rounded_rectangle([x, y, x + tw + 2 * pad_x, y + h], radius=22, fill=fill)
    d.text((x + pad_x, y + 9), text, font=f, fill=color)
    return x + tw + 2 * pad_x + 12


def mock_card(img, x, y, w, prompt, button, chips):
    """A miniature of the site UI: query box, main button, assistant chips."""
    d = ImageDraw.Draw(img)
    h = 330
    d.rounded_rectangle([x + 6, y + 10, x + w + 6, y + h + 10], radius=20, fill=(12, 16, 32))  # shadow
    d.rounded_rectangle([x, y, x + w, y + h], radius=20, fill=WHITE)
    # query box
    d.rounded_rectangle([x + 24, y + 24, x + w - 24, y + 120], radius=10, outline=(209, 213, 219), width=2, fill=(249, 250, 251))
    d.text((x + 40, y + 42), prompt, font=font(26, False), fill=(31, 41, 55))
    # buttons
    bw = (w - 48 - 16) // 2
    d.rounded_rectangle([x + 24, y + 140, x + 24 + bw, y + 196], radius=10, fill=(59, 130, 246))
    t = "Generate links"
    d.text((x + 24 + (bw - d.textlength(t, font=font(24))) / 2, y + 152), t, font=font(24), fill=WHITE)
    d.rounded_rectangle([x + 40 + bw, y + 140, x + w - 24, y + 196], radius=10, fill=(147, 51, 234))
    d.text((x + 40 + bw + (bw - d.textlength(button, font=font(24))) / 2, y + 152), button, font=font(24), fill=WHITE)
    # chips
    cx, cy = x + 24, y + 222
    f = font(22, False)
    for label in chips:
        nx = cx + d.textlength(label, font=f) + 48
        if nx > x + w - 24:
            cx, cy = x + 24, cy + 56
            if cy > y + h - 50:
                break
        cx = chip(d, cx, cy, label, f, (243, 244, 246), (55, 65, 81))


def og_base():
    img = gradient(300, 158, (17, 24, 39), (46, 16, 101)).resize((1200, 630), Image.BILINEAR)
    return img


def write_og_home():
    img = og_base()
    d = ImageDraw.Draw(img)
    img.paste(draw_icon(64), (80, 84), draw_icon(64))
    d.text((164, 96), "SearchGPT For Me", font=font(36), fill=(196, 181, 253))
    d.text((80, 200), "Let me ChatGPT", font=font(56), fill=WHITE)
    d.text((80, 270), "that for you.", font=font(56), fill=WHITE)
    d.text((80, 370), "One query. Every AI.", font=font(34, False), fill=(229, 231, 235))
    d.text((80, 425), "ChatGPT, Claude, Perplexity, Grok,", font=font(26, False), fill=(209, 213, 219))
    d.text((80, 461), "Google AI Mode + 20 more", font=font(26, False), fill=(209, 213, 219))
    d.text((80, 560), "searchgptforme.com", font=font(28), fill=WHITE)
    mock_card(img, 640, 130, 490, "How do I boil rice?", "Ask all AIs",
              ["ChatGPT", "Claude", "Perplexity", "Grok", "Google AI Mode", "Copilot", "Duck.ai"])
    img.save(os.path.join(ROOT, "og-image.png"), optimize=True)
    print("og-image.png written")


def write_og_engines():
    with open(os.path.join(ROOT, "engines.json")) as fh:
        data = json.load(fh)
    ai = next(g for g in data["groups"] if g["groupName"] == "AI Assistants")["engines"]
    os.makedirs(os.path.join(ROOT, "og"), exist_ok=True)
    for e in ai:
        short = e.get("shortName", e["name"])
        copy_only = e.get("prefill") == "none"
        img = og_base()
        d = ImageDraw.Draw(img)
        img.paste(draw_icon(64), (80, 84), draw_icon(64))
        d.text((164, 96), "SearchGPT For Me", font=font(36), fill=(196, 181, 253))
        title = e["name"]
        f = font(64) if d.textlength(e["name"], font=font(64)) < 520 else font(50)
        d.text((80, 200), title, font=f, fill=WHITE)
        d.text((80, 290), "prompt link generator", font=font(40, False), fill=(229, 231, 235))
        line = ("Copy a prompt and open " + short) if copy_only else ("Open " + short + " with your")
        d.text((80, 380), line, font=font(28, False), fill=(209, 213, 219))
        if not copy_only:
            d.text((80, 418), "prompt already filled in.", font=font(28, False), fill=(209, 213, 219))
        d.text((80, 560), "searchgptforme.com/" + e["slug"] + "/", font=font(26), fill=WHITE)
        others = [o.get("shortName", o["name"]) for o in ai if o["slug"] != e["slug"]][:5]
        mock_card(img, 640, 130, 490, "Explain quantum computing",
                  ("Copy prompt" if copy_only else "Open in " + short), [short] + others)
        img.save(os.path.join(ROOT, "og", e["slug"] + ".png"), optimize=True)
    print("og/*.png written:", len(ai))


if __name__ == "__main__":
    write_icons()
    write_og_home()
    write_og_engines()
