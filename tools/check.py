#!/usr/bin/env python3
"""Validate the generated site: engines.json, HTML tag balance, JSON-LD blocks,
og:image files and the absence of the Tailwind CDN on every page.

Run from the repository root:  python3 tools/check.py
"""
import glob
import html.parser
import json
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SITE = "https://searchgptforme.com"


class TagBalance(html.parser.HTMLParser):
    VOID = {"meta", "link", "img", "input", "br", "hr"}

    def __init__(self):
        super().__init__()
        self.stack = []
        self.errors = []

    def handle_starttag(self, tag, attrs):
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack[-1] != tag:
            self.errors.append(f"unexpected </{tag}> at {self.getpos()}")
        else:
            self.stack.pop()


def main():
    problems = []
    with open(os.path.join(ROOT, "public", "engines.json")) as fh:
        json.load(fh)

    pages = [os.path.join(ROOT, "public", "index.html")]
    pages += sorted(glob.glob(os.path.join(ROOT, "public", "*", "index.html")))
    for page in pages:
        rel = os.path.relpath(page, ROOT)
        with open(page) as fh:
            src = fh.read()

        parser = TagBalance()
        parser.feed(src)
        for err in parser.errors:
            problems.append(f"{rel}: {err}")
        if parser.stack:
            problems.append(f"{rel}: unclosed tags {parser.stack}")

        for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', src, re.S):
            try:
                json.loads(block)
            except json.JSONDecodeError as exc:
                problems.append(f"{rel}: invalid JSON-LD: {exc}")

        og = re.search(r'property="og:image" content="' + re.escape(SITE) + r'(/[^"]+)"', src)
        if not og:
            problems.append(f"{rel}: no og:image")
        elif not os.path.exists(os.path.join(ROOT, "public", og.group(1).lstrip("/"))):
            problems.append(f"{rel}: og:image file missing: {og.group(1)}")

        if "tailwindcss" in src:
            problems.append(f"{rel}: still references the Tailwind CDN")

    for p in problems:
        print("ERROR", p)
    if problems:
        sys.exit(1)
    print(f"{len(pages)} pages ok")


if __name__ == "__main__":
    main()
