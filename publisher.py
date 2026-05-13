"""
GitHub Pages publisher.
Generates a Jekyll-compatible Markdown post from a digest dict
and writes it to the _posts/ directory for GitHub Actions to commit.
"""

import os
import re
from datetime import datetime
from pathlib import Path


POSTS_DIR = Path("_posts")


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

    # Build story sections
    stories_md = ""
    for story in digest["stories"]:
        stories_md += f"### {story['headline']}\n\n{story['summary']}\n\n"

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

*Generated every Sunday by [Claude](https://anthropic.com) with web search.*
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
