# Project commands. Install `just`: https://github.com/casey/just
# List recipes: `just`

set shell := ["bash", "-euo", "pipefail", "-c"]

port := "8080"

# show available recipes
default:
    @just --list

# serve public/ for manual testing in a browser (http://localhost:8080)
serve port=port:
    @echo "http://localhost:{{port}}/"
    python3 -m http.server {{port}} --bind 127.0.0.1 --directory public

# regenerate index.html data, per-AI pages and sitemap from public/engines.json
generate:
    go run ./cmd/generate

# redraw favicons, touch icons and Open Graph images from public/icon.svg (needs Pillow)
images:
    python3 tools/images.py

# regenerate everything: pages and images
build: generate images

# validate: go vet, engines.json, HTML tag balance, JSON-LD and og:image files on every page
check:
    go vet ./...
    python3 tools/check.py

# check that generated files are up to date with engines.json and templates (for CI or before commit)
verify-generated: generate
    git diff --exit-code --stat -- public ':!public/og' ':!public/*.png' ':!public/*.ico'

# open the local server in the default browser
open port=port:
    xdg-open "http://localhost:{{port}}/" 2>/dev/null || open "http://localhost:{{port}}/"
