"""
Jekyll publisher for the Forecasting Digest.
Writes a post to _posts/ with news, papers, and social drafts sections.
"""

import re
from datetime import datetime
from pathlib import Path

POSTS_DIR = Path("_posts")


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:60].rstrip("-")


def build_forecasting_post(news: dict, pubs: dict, date: datetime) -> str:
    date_str = date.strftime("%B %d, %Y")
    iso_date = date.strftime("%Y-%m-%d")
    title    = f"Forecasting Digest — {date_str}"

    # Stories — include source badge and clickable links
    stories_md = ""
    for story in news.get("stories", []):
        source = f" *({story.get('source', '')})*" if story.get("source") else ""
        links = story.get("links") or []
        if isinstance(links, str):
            links = [links]
        links_md = ""
        if links:
            parts = [f"[Source]({url})" for url in links if isinstance(url, str) and url.startswith("http")]
            if parts:
                links_md = f"\n\n{' · '.join(parts)}"
        stories_md += f"### {story['headline']}{source}\n\n{story['summary']}{links_md}\n\n"

    # Papers
    papers_md = ""
    for paper in pubs.get("papers", []):
        papers_md += (
            f"#### {paper['title']}\n\n"
            f"**{paper.get('authors', '')}** · *{paper.get('venue', '')}*"
            + (f" · `{paper.get('url_hint', '')}`" if paper.get("url_hint") else "")
            + f"\n\n{paper['summary']}\n\n"
        )

    return f"""---
layout: post
title: "{title}"
date: {iso_date}
description: "{news.get('intro', '')}"
categories: [digest, forecasting]
---

{news.get('intro', '')}

---

## Industry news

{stories_md}
> **What to watch:** {news.get('watch', '')}

---

## Recent publications

{papers_md}
---

*Generated every Saturday by [Claude](https://anthropic.com) with web search.*
"""


def publish_forecasting_post(news: dict, pubs: dict, social: dict) -> Path:
    now      = datetime.today()
    iso_date = now.strftime("%Y-%m-%d")

    first_story = news.get("stories", [{}])[0].get("headline", "forecasting-digest")
    slug     = slugify(first_story)
    filename = POSTS_DIR / f"{iso_date}-forecasting-{slug}.md"

    POSTS_DIR.mkdir(exist_ok=True)
    filename.write_text(
        build_forecasting_post(news, pubs, now),
        encoding="utf-8"
    )
    print(f"📝  Forecasting post written → {filename}")
    return filename
