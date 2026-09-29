# SearchGPT For Me

**Let me ChatGPT that for you.** One query, every AI.

https://searchgptforme.com

Type a question once and get links that open it in ChatGPT, Claude, Perplexity, Grok,
Google AI Mode, Microsoft Copilot, DuckDuckGo AI Chat, plus 20+ search engines and
communities (Google, Bing, Reddit, Stack Overflow, Hacker News, GitHub, YouTube, ...).
Each AI link carries the prompt, so the assistant opens with the question already filled in.

- **Ask all AIs**: open the selected assistants in new tabs with one click.
- **Shareable links**: `https://searchgptforme.com/?q=your+question`.
- **Address bar**: the site ships an OpenSearch description, so browsers can add it as a search
  engine. Per-assistant shortcuts: `https://searchgptforme.com/chatgpt/?go=1&q=%s`.
- **Per-assistant pages**: `/chatgpt/`, `/claude/`, `/perplexity/`, `/grok/`, `/google-ai-mode/`,
  `/copilot/`, `/duckduckgo-ai-chat/`, `/gemini/`, `/mistral/`.

Static site, no backend: everything lives in `public/`.

- **Dark theme**: follows the system setting, with a toggle in the header.
- **Languages**: English at `/`, plus `/uk/`, `/es/`, `/de/`, `/fr/`, `/pt/`, `/pl/` and `/it/`, with `hreflang` alternates.
- **Bookmarklet** and **Android share target**: send selected text or a shared page to the AIs.

## Development

With [`just`](https://github.com/casey/just) installed, `just` lists the project commands:
`just serve` starts a local server on http://localhost:8080 for manual testing in a browser,
`just build` regenerates pages and images, `just check` validates the result.
The underlying commands are below.

Every HTML page is generated. Sources:

- `public/engines.json`: the single source of truth for all services;
- `locales/<code>.json`: every string of the UI and the long-form text, one file per language
  (`en` is the default and lives at `/`, any other locale lives at `/<code>/`);
- `templates/index.html`, `templates/engine.html`, `templates/_shared.html`: Go `html/template` files.

After editing any of them run

```sh
go run ./cmd/generate
```

which renders `public/index.html`, `public/<locale>/index.html`, one `public/[<locale>/]<slug>/index.html`
per AI assistant, and `public/sitemap-main.xml` with `hreflang` alternates. Do not edit the generated
files by hand. To add a language, copy `locales/en.json`, translate it, and add its texts to
`OG_TEXT` in `tools/images.py` (the script refuses to run while the two disagree). Removing a locale
or an assistant also removes its generated pages on the next run.

Icons and Open Graph images are generated too. `public/icon.svg` is the vector source; run

```sh
python3 tools/images.py
```

(needs Pillow) to redraw all favicon, touch and tile PNGs, `favicon.ico`, `og-image.png`,
one `public/og/<slug>.png` per AI assistant, and the same set per extra locale under `public/og/<code>/`.

CI (`.github/workflows/ci.yml`) runs `just check` and `just verify-generated`, so a pull request that
changes the sources without regenerating the pages fails.

Serve `public/` with any static file server, for example `python3 -m http.server -d public`.

## License

MIT
