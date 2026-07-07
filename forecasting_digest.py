"""
Weekly Forecasting Digest
Fetches business/supply chain forecasting news + recent academic publications
via web search (Claude, falling back to GPT), sends an email via Resend,
publishes a Jekyll post, and generates draft LinkedIn + X (Twitter) posts
for the week.
"""

import os
import resend
from datetime import datetime
from ai_client import call_llm_with_search
from forecasting_email_template import build_forecasting_email
from forecasting_publisher import publish_forecasting_post

# ── Config ───────────────────────────────────────────────────────────────────
RESEND_API_KEY    = os.environ["RESEND_API_KEY"]
FROM_EMAIL        = os.environ["FROM_EMAIL"]
TO_EMAILS         = os.environ["TO_EMAILS_FORECASTING"].split(",")
TOPICS            = os.environ.get(
    "TOPICS_FORECASTING",
    "supply chain forecasting, demand planning, time series forecasting, "
    "inventory optimization, S&OP, business forecasting"
)
JOURNALS          = os.environ.get(
    "JOURNALS",
    "International Journal of Forecasting, Journal of Forecasting, "
    "Operations Research, Management Science, arXiv stat.ML, arXiv cs.LG, SSRN"
)

# ── Prompts ───────────────────────────────────────────────────────────────────
NEWS_PROMPT = """You are a senior supply chain and forecasting analyst writing a weekly digest
for data scientists and forecasting practitioners.

Search for the most important business/supply chain forecasting news from the past 7 days
covering: {topics}.

Focus on: vendor announcements, enterprise AI/ML forecasting tools, S&OP trends,
real-world demand forecasting case studies, and industry analyst reports.

Include 4-5 stories with plain-text headlines (no markdown bold).
For each story include the publication/site name and at least one direct source URL.
Prioritise practitioner relevance over academic theory."""

PUBLICATIONS_PROMPT = """You are a forecasting researcher helping a data scientist stay current
with the academic literature.

Search for forecasting-related papers and publications from the past 14 days in:
{journals}

Focus on: probabilistic forecasting, neural forecasting, LLMs for time series,
supply chain optimisation, demand forecasting methods, and ensemble approaches.

Include 3-5 papers. For EACH paper, provide a proper citation (authors and venue),
its arXiv ID or DOI, and at least one direct working URL (arXiv abstract page,
publisher page, or DOI link) so the reader can verify and open the source.
Prioritise papers with practical forecasting relevance."""

SOCIAL_PROMPT = """You are a social media strategist helping a Lead Data Scientist share
forecasting insights professionally.

Given this week's forecasting digest:
INTRO: {intro}
TOP STORIES: {stories}
NEW PAPERS: {papers}

Write a LinkedIn post (150-200 words, professional tone, ends with 2-3 relevant hashtags)
and three X posts (max 280 chars each: one punchy insight, one paper highlight, one hot take).
LinkedIn tone: thoughtful practitioner. X tone: direct, opinionated, technically credible."""

# ── Output tool schemas ────────────────────────────────────────────────────────
# Each tool is used in phase 2 of _call_llm to force structured output.
# The model must populate the schema — the API validates it, eliminating text JSON parsing.

NEWS_TOOL: dict = {
    "name": "submit_news",
    "description": "Submit the weekly forecasting industry news digest.",
    "input_schema": {
        "type": "object",
        "properties": {
            "intro": {"type": "string", "description": "One punchy sentence summarising the week."},
            "stories": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "headline": {"type": "string"},
                        "summary":  {"type": "string", "description": "2-3 sentence summary."},
                        "source":   {"type": "string", "description": "Publication or site name."},
                        "links": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "At least one direct source URL per story.",
                        },
                    },
                    "required": ["headline", "summary", "source", "links"],
                },
            },
            "watch": {"type": "string", "description": "One closing sentence on what to track."},
        },
        "required": ["intro", "stories", "watch"],
    },
}

PUBLICATIONS_TOOL: dict = {
    "name": "submit_publications",
    "description": "Submit recent forecasting academic papers.",
    "input_schema": {
        "type": "object",
        "properties": {
            "papers": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title":      {"type": "string"},
                        "authors":    {"type": "string"},
                        "venue":      {"type": "string"},
                        "identifier": {
                            "type": "string",
                            "description": "arXiv ID (e.g. arXiv:2401.01234) or DOI, for proper citation.",
                        },
                        "summary":    {"type": "string", "description": "2-3 sentences on contribution and practitioner relevance."},
                        "links": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "At least one direct working URL to the paper "
                                "(arXiv abstract page, publisher page, or DOI link)."
                            ),
                        },
                    },
                    "required": ["title", "authors", "venue", "identifier", "summary", "links"],
                },
            },
        },
        "required": ["papers"],
    },
}

SOCIAL_TOOL: dict = {
    "name": "submit_social",
    "description": "Submit drafted LinkedIn and X social media posts.",
    "input_schema": {
        "type": "object",
        "properties": {
            "linkedin": {
                "type": "object",
                "properties": {
                    "post": {"type": "string"},
                    "hook": {"type": "string"},
                },
                "required": ["post", "hook"],
            },
            "x_posts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                },
            },
        },
        "required": ["linkedin", "x_posts"],
    },
}


def _is_http_url(value) -> bool:
    return isinstance(value, str) and (value.startswith("http://") or value.startswith("https://"))


def _fallback_paper_link(title: str) -> str:
    # Google Scholar search is a decent "verify it yourself" fallback when the
    # model doesn't return a canonical URL. Keeps every paper clickable.
    from urllib.parse import quote_plus

    q = quote_plus(title or "forecasting research")
    return f"https://scholar.google.com/scholar?q={q}"


def normalize_publications(pubs: dict) -> dict:
    """
    Ensure a stable publications shape and at least one working link per
    paper. Guards against occasional model schema drift or missing URLs.
    """
    papers = pubs.get("papers") if isinstance(pubs, dict) else None
    if not isinstance(papers, list):
        papers = []

    normalized_papers = []
    for paper in papers:
        if not isinstance(paper, dict):
            continue

        title = (paper.get("title") or "").strip()

        links_raw = paper.get("links", [])
        if isinstance(links_raw, str):
            links_raw = [links_raw]
        if not isinstance(links_raw, list):
            links_raw = []

        links = []
        for link in links_raw:
            if isinstance(link, dict):
                link = link.get("url")
            if _is_http_url(link):
                links.append(link)

        if not links:
            links = [_fallback_paper_link(title)]

        normalized_papers.append(
            {
                "title":      title,
                "authors":    (paper.get("authors") or "").strip(),
                "venue":      (paper.get("venue") or "").strip(),
                "identifier": (paper.get("identifier") or "").strip(),
                "summary":    (paper.get("summary") or "").strip(),
                "links":      links,
            }
        )

    pubs["papers"] = normalized_papers
    return pubs


def _call_llm(system: str, user: str, output_tool: dict) -> tuple:
    """
    Two-phase "search then extract structured output" call, tried first
    against Claude and automatically falling back to GPT if Claude errors
    out. Returns (structured_output, provider_label).
    """
    today    = datetime.today().strftime("%B %d, %Y")
    user_msg = f"Today is {today}. {user}"

    return call_llm_with_search(system=system, user_msg=user_msg, output_tool=output_tool)


def fetch_news() -> tuple:
    print("  → Fetching industry news...")
    return _call_llm(
        system=NEWS_PROMPT.format(topics=TOPICS),
        user="Search for this week's top supply chain and business forecasting news.",
        output_tool=NEWS_TOOL,
    )


def fetch_publications() -> tuple:
    print("  → Fetching recent publications...")
    pubs, provider = _call_llm(
        system=PUBLICATIONS_PROMPT.format(journals=JOURNALS),
        user="Search for forecasting papers published in the past 14 days.",
        output_tool=PUBLICATIONS_TOOL,
    )
    return normalize_publications(pubs), provider


def generate_social_posts(news: dict, pubs: dict) -> tuple:
    print("  → Drafting LinkedIn + X posts...")
    stories_text = "\n".join(
        f"- {s['headline']}: {s['summary']}" for s in news.get("stories", [])
    )
    papers_text = "\n".join(
        f"- {p['title']} ({p['venue']}): {p['summary']}"
        for p in pubs.get("papers", [])
    )
    return _call_llm(
        system=SOCIAL_PROMPT.format(
            intro=news.get("intro", ""),
            stories=stories_text,
            papers=papers_text,
        ),
        user="Generate the LinkedIn post and three X posts now.",
        output_tool=SOCIAL_TOOL,
    )


def send_email(news: dict, pubs: dict, social: dict) -> str:
    resend.api_key = RESEND_API_KEY
    today     = datetime.today().strftime("%B %d, %Y")
    subject   = f"Forecasting Digest — {today}"
    html_body = build_forecasting_email(news, pubs, social, today)
    plain_body = _build_plain_text(news, pubs, social)

    params: resend.Emails.SendParams = {
        "from":    FROM_EMAIL,
        "to":      TO_EMAILS,
        "subject": subject,
        "html":    html_body,
        "text":    plain_body,
    }
    result: resend.Emails.SendResponse = resend.Emails.send(params)
    return result["id"]


def _build_plain_text(news: dict, pubs: dict, social: dict) -> str:
    lines = ["── FORECASTING DIGEST ──", "", news.get("intro", ""), ""]

    lines.append("INDUSTRY NEWS")
    lines.append("─" * 40)
    for i, s in enumerate(news.get("stories", []), 1):
        lines.append(f"{i}. {s['headline']} ({s.get('source', '')})")
        lines.append(s["summary"])
        story_links = [u for u in (s.get("links") or []) if isinstance(u, str) and u.startswith("http")]
        if story_links:
            lines.append(f"Source: {story_links[0]}")
        lines.append("")

    lines += [f"What to watch: {news.get('watch', '')}", ""]

    lines.append("RECENT PUBLICATIONS")
    lines.append("─" * 40)
    for p in pubs.get("papers", []):
        citation = f"{p.get('authors', '')} · {p.get('venue', '')}"
        if p.get("identifier"):
            citation += f" · {p['identifier']}"
        lines += [f"{p['title']}", citation, p["summary"]]
        paper_links = [u for u in (p.get("links") or []) if isinstance(u, str) and u.startswith("http")]
        if paper_links:
            lines.append(f"Read it: {paper_links[0]}")
        lines.append("")

    lines.append("SOCIAL DRAFTS")
    lines.append("─" * 40)
    li = social.get("linkedin", {})
    lines += ["LinkedIn:", li.get("post", ""), ""]
    for i, t in enumerate(social.get("x_posts", []), 1):
        lines.append(f"X ({i}): {t.get('text', '')}")

    return "\n".join(lines)


def main():
    print("⏳  Building this week's forecasting digest...")

    news,   news_provider   = fetch_news()
    pubs,   pubs_provider   = fetch_publications()
    social, social_provider = generate_social_posts(news, pubs)

    # Distinct providers actually used this run, in call order (dict preserves
    # insertion order and de-dupes), so the post footer stays accurate even if
    # one call fell back to GPT while the others stayed on Claude.
    providers = list(dict.fromkeys([news_provider, pubs_provider, social_provider]))

    print(f"✅  {len(news.get('stories', []))} news stories, "
          f"{len(pubs.get('papers', []))} papers, social drafts ready "
          f"(via {', '.join(providers)}).")

    print("📧  Sending email via Resend...")
    email_id = send_email(news, pubs, social)
    print(f"✅  Sent! Email ID: {email_id}")

    print("📝  Publishing to GitHub Pages...")
    publish_forecasting_post(news, pubs, social, providers)
    print("✅  Post written. GitHub Actions will commit and deploy.")


if __name__ == "__main__":
    main()
