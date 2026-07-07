"""
Jekyll publisher for the Forecasting Digest.
Writes a post to _posts/ with news, papers, and social drafts sections.
"""

import re
from datetime import datetime
from pathlib import Path

POSTS_DIR = Path("_posts")


def _provider_credit(providers) -> str:
    """Render a footer credit line linking to whichever provider(s) generated the digest."""
    providers = providers or ["Claude"]
    links = []
    for provider in providers:
        url = "https://openai.com" if provider.lower().startswith("openai") else "https://anthropic.com"
        links.append(f"[{provider}]({url})")
    return " and ".join(links)


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:60].rstrip("-")


def build_forecasting_post(news: dict, pubs: dict, date: datetime, providers=None) -> str:
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

    # Papers — include full citation (authors, venue, arXiv ID/DOI) and clickable links
    papers_md = ""
    for paper in pubs.get("papers", []):
        citation_bits = []
        if paper.get("authors"):
            citation_bits.append(f"**{paper['authors']}**")
        if paper.get("venue"):
            citation_bits.append(f"*{paper['venue']}*")
        if paper.get("identifier"):
            citation_bits.append(f"`{paper['identifier']}`")
        citation_line = " · ".join(citation_bits)

        paper_links = paper.get("links") or []
        if isinstance(paper_links, str):
            paper_links = [paper_links]
        link_parts = [
            f"[Read paper]({url})" if i == 0 else f"[Link {i + 1}]({url})"
            for i, url in enumerate(paper_links)
            if isinstance(url, str) and url.startswith("http")
        ]
        links_md = f"\n\n{' · '.join(link_parts)}" if link_parts else ""

        papers_md += f"#### {paper['title']}\n\n{citation_line}\n\n{paper['summary']}{links_md}\n\n"

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

*Generated every Saturday by {_provider_credit(providers)} with web search.*
"""


def publish_forecasting_post(news: dict, pubs: dict, social: dict, providers=None) -> Path:
    now      = datetime.today()
    iso_date = now.strftime("%Y-%m-%d")

    first_story = news.get("stories", [{}])[0].get("headline", "forecasting-digest")
    slug     = slugify(first_story)
    filename = POSTS_DIR / f"{iso_date}-forecasting-{slug}.md"

    POSTS_DIR.mkdir(exist_ok=True)
    filename.write_text(
        build_forecasting_post(news, pubs, now, providers),
        encoding="utf-8"
    )
    print(f"📝  Forecasting post written → {filename}")
    return filename
