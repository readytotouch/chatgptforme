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

## Development

`public/engines.json` is the single source of truth for all services. After editing it run

```sh
go run ./cmd/generate
```

which rewrites the engine list and the AI assistants table inside `public/index.html`
(between the `engines:start` / `ai-table:start` markers), renders `public/<slug>/index.html`
for every AI assistant from `templates/engine.html`, and regenerates `public/sitemap-main.xml`.

Icons and Open Graph images are generated too. `public/icon.svg` is the vector source; run

```sh
python3 tools/images.py
```

(needs Pillow) to redraw all favicon, touch and tile PNGs, `favicon.ico`, `og-image.png`
and one `public/og/<slug>.png` per AI assistant.

Serve `public/` with any static file server, for example `python3 -m http.server -d public`.

## License

MIT
