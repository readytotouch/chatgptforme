#!/usr/bin/env python3
"""Generate every raster image of the site from code: favicons, touch icons,
tile icons, favicon.ico, the Open Graph image and one OG image per AI assistant.

Run from the repository root:  python3 tools/images.py
Requires Pillow. The vector source of the icon is public/icon.svg; this script
redraws the same geometry with Pillow because no SVG rasteriser is assumed.
"""
import glob
import json
import os
import sys

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


def fit_font(d, text, max_width, size=24, bold=True):
    """Largest bold font up to `size` whose rendering of `text` fits in max_width."""
    while size > 12 and d.textlength(text, font=font(size, bold)) > max_width:
        size -= 1
    return font(size, bold)


def mock_card(img, x, y, w, prompt, button, chips, generate="Generate links"):
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
    f = fit_font(d, generate, bw - 20)
    d.text((x + 24 + (bw - d.textlength(generate, font=f)) / 2, y + 168 - f.size / 2 - 2), generate, font=f, fill=WHITE)
    d.rounded_rectangle([x + 40 + bw, y + 140, x + w - 24, y + 196], radius=10, fill=(147, 51, 234))
    f = fit_font(d, button, bw - 20)
    d.text((x + 40 + bw + (bw - d.textlength(button, font=f)) / 2, y + 168 - f.size / 2 - 2), button, font=f, fill=WHITE)
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


_ICON64 = None


def icon64():
    """The 64 px icon pasted on every OG image, drawn once."""
    global _ICON64
    if _ICON64 is None:
        _ICON64 = draw_icon(64)
    return _ICON64


def og_base():
    img = gradient(300, 158, (17, 24, 39), (46, 16, 101)).resize((1200, 630), Image.BILINEAR)
    return img


# Text for the OG images per locale. Keys must match the codes in locales/*.json;
# file locations derive from the code (see og_paths).
OG_TEXT = {
    "en": {
        "headline": ["Let me ChatGPT", "that for you."],
        "sub": "One query. Every AI.",
        "list": ["ChatGPT, Claude, Perplexity, Grok,", "Google AI Mode + 20 more"],
        "prompt": "How do I boil rice?", "generate": "Generate links", "ask_all": "Ask all AIs",
        "e_sub": "prompt link generator",
        "e_open": ["Open {short} with your", "prompt already filled in."],
        "e_copy": ["Copy a prompt and open {short}", ""],
        "e_prompt": "Explain quantum computing", "e_open_btn": "Open in {short}", "e_copy_btn": "Copy prompt",
    },
    "uk": {
        "headline": ["Хай ChatGPT відповість", "за тебе."],
        "sub": "Один запит. Кожен ШІ.",
        "list": ["ChatGPT, Claude, Perplexity, Grok,", "Google AI Mode + ще 20"],
        "prompt": "Як зварити рис?", "generate": "Створити посилання", "ask_all": "Запитати всі ШІ",
        "e_sub": "генератор посилань з промптом",
        "e_open": ["Відкрий {short} з уже", "введеним промптом."],
        "e_copy": ["Скопіюй промпт і відкрий {short}", ""],
        "e_prompt": "Поясни квантові обчислення", "e_open_btn": "Відкрити в {short}", "e_copy_btn": "Копіювати промпт",
    },
    "es": {
        "headline": ["Deja que ChatGPT", "responda por ti."],
        "sub": "Una consulta. Todas las IA.",
        "list": ["ChatGPT, Claude, Perplexity, Grok,", "Google AI Mode + 20 más"],
        "prompt": "¿Cómo cocinar arroz?", "generate": "Generar enlaces", "ask_all": "Preguntar a todas las IA",
        "e_sub": "generador de enlaces con prompt",
        "e_open": ["Abre {short} con tu", "prompt ya escrito."],
        "e_copy": ["Copia un prompt y abre {short}", ""],
        "e_prompt": "Explica la computación cuántica", "e_open_btn": "Abrir en {short}", "e_copy_btn": "Copiar prompt",
    },
    "de": {
        "headline": ["Lass ChatGPT das", "für dich beantworten."],
        "sub": "Eine Frage. Jede KI.",
        "list": ["ChatGPT, Claude, Perplexity, Grok,", "Google AI Mode + 20 weitere"],
        "prompt": "Wie kocht man Reis?", "generate": "Links erzeugen", "ask_all": "Alle KIs fragen",
        "e_sub": "Prompt-Link-Generator",
        "e_open": ["Öffne {short} mit bereits", "eingetragenem Prompt."],
        "e_copy": ["Prompt kopieren und {short} öffnen", ""],
        "e_prompt": "Erkläre Quantencomputer", "e_open_btn": "In {short} öffnen", "e_copy_btn": "Prompt kopieren",
    },
    "fr": {
        "headline": ["Laissez ChatGPT", "répondre pour vous."],
        "sub": "Une question. Toutes les IA.",
        "list": ["ChatGPT, Claude, Perplexity, Grok,", "Google AI Mode + 20 autres"],
        "prompt": "Comment cuire du riz ?", "generate": "Générer les liens", "ask_all": "Demander à toutes les IA",
        "e_sub": "générateur de liens avec prompt",
        "e_open": ["Ouvrez {short} avec votre", "prompt déjà saisi."],
        "e_copy": ["Copiez un prompt et ouvrez {short}", ""],
        "e_prompt": "Explique l'informatique quantique", "e_open_btn": "Ouvrir dans {short}", "e_copy_btn": "Copier le prompt",
    },
    "pt": {
        "headline": ["Deixe o ChatGPT", "responder por você."],
        "sub": "Uma pergunta. Todas as IAs.",
        "list": ["ChatGPT, Claude, Perplexity, Grok,", "Google AI Mode + mais 20"],
        "prompt": "Como cozinhar arroz?", "generate": "Gerar links", "ask_all": "Perguntar a todas as IAs",
        "e_sub": "gerador de links com prompt",
        "e_open": ["Abra o {short} com o seu", "prompt já preenchido."],
        "e_copy": ["Copie um prompt e abra o {short}", ""],
        "e_prompt": "Explique computação quântica", "e_open_btn": "Abrir no {short}", "e_copy_btn": "Copiar prompt",
    },
    "pl": {
        "headline": ["Niech ChatGPT", "odpowie za ciebie."],
        "sub": "Jedno pytanie. Każde AI.",
        "list": ["ChatGPT, Claude, Perplexity, Grok,", "Google AI Mode + 20 innych"],
        "prompt": "Jak ugotować ryż?", "generate": "Wygeneruj linki", "ask_all": "Zapytaj wszystkie AI",
        "e_sub": "generator linków z promptem",
        "e_open": ["Otwórz {short} z już", "wpisanym promptem."],
        "e_copy": ["Skopiuj prompt i otwórz {short}", ""],
        "e_prompt": "Wyjaśnij obliczenia kwantowe", "e_open_btn": "Otwórz w {short}", "e_copy_btn": "Kopiuj prompt",
    },
    "it": {
        "headline": ["Lascia che ChatGPT", "risponda per te."],
        "sub": "Una domanda. Tutte le IA.",
        "list": ["ChatGPT, Claude, Perplexity, Grok,", "Google AI Mode + altri 20"],
        "prompt": "Come cuocere il riso?", "generate": "Genera i link", "ask_all": "Chiedi a tutte le IA",
        "e_sub": "generatore di link con prompt",
        "e_open": ["Apri {short} con il tuo", "prompt già scritto."],
        "e_copy": ["Copia un prompt e apri {short}", ""],
        "e_prompt": "Spiega il calcolo quantistico", "e_open_btn": "Apri in {short}", "e_copy_btn": "Copia prompt",
    },
}


def og_paths(loc):
    """(URL path prefix, home image file, directory for per-assistant images) for a locale code."""
    if loc == "en":
        return "", "og-image.png", "og"
    return "/" + loc, f"og/{loc}/home.png", f"og/{loc}"


def locale_codes():
    return sorted(os.path.basename(f)[:-5] for f in glob.glob(os.path.join(ROOT, "..", "locales", "*.json")))


def load_ai_engines():
    with open(os.path.join(ROOT, "engines.json")) as fh:
        data = json.load(fh)
    return next(g for g in data["groups"] if g["groupName"] == "AI Assistants")["engines"]


def write_og_home(loc):
    t = OG_TEXT[loc]
    path, home_file, _ = og_paths(loc)
    img = og_base()
    d = ImageDraw.Draw(img)
    img.paste(icon64(), (80, 84), icon64())
    d.text((164, 96), "SearchGPT For Me", font=font(36), fill=(196, 181, 253))
    hf = fit_font(d, max(t["headline"], key=len), 530, 56)
    d.text((80, 200), t["headline"][0], font=hf, fill=WHITE)
    d.text((80, 200 + hf.size + 14), t["headline"][1], font=hf, fill=WHITE)
    d.text((80, 370), t["sub"], font=font(34, False), fill=(229, 231, 235))
    d.text((80, 425), t["list"][0], font=font(26, False), fill=(209, 213, 219))
    d.text((80, 461), t["list"][1], font=font(26, False), fill=(209, 213, 219))
    d.text((80, 560), "searchgptforme.com" + path, font=font(28), fill=WHITE)
    mock_card(img, 640, 130, 490, t["prompt"], t["ask_all"],
              ["ChatGPT", "Claude", "Perplexity", "Grok", "Google AI Mode", "Copilot", "Duck.ai"], t["generate"])
    out = os.path.join(ROOT, home_file)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    img.save(out, optimize=True)
    print(home_file, "written")


def write_og_engines(loc, ai):
    t = OG_TEXT[loc]
    path, _, engine_dir = og_paths(loc)
    os.makedirs(os.path.join(ROOT, engine_dir), exist_ok=True)
    for e in ai:
        short = e.get("shortName", e["name"])
        copy_only = e.get("prefill") == "none"
        img = og_base()
        d = ImageDraw.Draw(img)
        img.paste(icon64(), (80, 84), icon64())
        d.text((164, 96), "SearchGPT For Me", font=font(36), fill=(196, 181, 253))
        f = font(64) if d.textlength(e["name"], font=font(64)) < 520 else font(50)
        d.text((80, 200), e["name"], font=f, fill=WHITE)
        sf = font(40, False) if d.textlength(t["e_sub"], font=font(40, False)) < 540 else font(32, False)
        d.text((80, 290), t["e_sub"], font=sf, fill=(229, 231, 235))
        lines = t["e_copy"] if copy_only else t["e_open"]
        for i, line in enumerate(lines):
            if line:
                d.text((80, 380 + i * 38), line.replace("{short}", short), font=font(28, False), fill=(209, 213, 219))
        d.text((80, 560), "searchgptforme.com" + path + "/" + e["slug"] + "/", font=font(26), fill=WHITE)
        others = [o.get("shortName", o["name"]) for o in ai if o["slug"] != e["slug"]][:5]
        button = (t["e_copy_btn"] if copy_only else t["e_open_btn"]).replace("{short}", short)
        mock_card(img, 640, 130, 490, t["e_prompt"], button, [short] + others, t["generate"])
        img.save(os.path.join(ROOT, engine_dir, e["slug"] + ".png"), optimize=True)
    print(engine_dir + "/*.png written:", len(ai))


if __name__ == "__main__":
    codes = locale_codes()
    missing = sorted(set(codes) - set(OG_TEXT))
    extra = sorted(set(OG_TEXT) - set(codes))
    if missing or extra:
        sys.exit(f"OG_TEXT and locales/*.json disagree: missing {missing}, extra {extra}")
    write_icons()
    ai = load_ai_engines()
    for loc in codes:
        write_og_home(loc)
        write_og_engines(loc, ai)
