"""
GitHub Pages publisher.
Generates a Jekyll-compatible Markdown post from a digest dict
and writes it to the _posts/ directory for GitHub Actions to commit.
"""

import os
import re
from datetime import datetime
from pathlib import Path

from categories import category_label

POSTS_DIR = Path("_posts")


def _provider_credit(provider: str) -> str:
    """Render a footer credit line linking to whichever provider actually generated the digest."""
    provider = provider or "Claude"
    if provider.lower().startswith("openai"):
        return f"[{provider}](https://openai.com)"
    return f"[{provider}](https://anthropic.com)"


def slugify(text: str) -> str:
    """Convert a headline to a URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:60].rstrip("-")


def build_markdown_post(digest: dict, date: datetime) -> str:
    """Render digest dict as a Jekyll front-matter Markdown post."""
    date_str      = date.strftime("%B %d, %Y")
    iso_date      = date.strftime("%Y-%m-%d")
    title         = f"AI News Digest — {date_str}"
    first_headline = digest["stories"][0]["headline"] if digest["stories"] else ""

    # Build story sections — include category tag and source links
    stories_md = ""
    for story in digest["stories"]:
        category = f" `{category_label(story.get('category'))}`"
        links = story.get("links") or []
        if isinstance(links, str):
            links = [links]
        parts = [f"[Source]({url})" for url in links if isinstance(url, str) and url.startswith("http")]
        links_md = f"\n\n{' · '.join(parts)}" if parts else ""
        stories_md += f"### {story['headline']}{category}\n\n{story['summary']}{links_md}\n\n"

    return f"""---
layout: post
title: "{title}"
date: {iso_date}
description: "{digest['intro']}"
categories: [digest, ai-news]
---

{digest['intro']}

---

{stories_md}## What to watch

{digest['watch']}

---

*Generated every Sunday by {_provider_credit(digest.get("provider"))} with web search.*
"""


def publish_post(digest: dict) -> Path:
    """Write the Markdown post file and return its path."""
    now      = datetime.today()
    iso_date = now.strftime("%Y-%m-%d")
    slug     = slugify(digest["stories"][0]["headline"]) if digest["stories"] else "weekly-digest"
    filename = POSTS_DIR / f"{iso_date}-{slug}.md"

    POSTS_DIR.mkdir(exist_ok=True)
    filename.write_text(build_markdown_post(digest, now), encoding="utf-8")
    print(f"📝  Post written → {filename}")
    return filename
