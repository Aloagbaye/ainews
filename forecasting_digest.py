"""
Weekly Forecasting Digest
Fetches business/supply chain forecasting news + recent academic publications
via Claude web_search, sends an email via Resend, publishes a Jekyll post,
and generates draft LinkedIn + X (Twitter) posts for the week.
"""

import os
import anthropic
import resend
from datetime import datetime
from forecasting_email_template import build_forecasting_email
from forecasting_publisher import publish_forecasting_post

# ── Config ───────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
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

Include 4-5 stories with plain-text headlines (no markdown bold). Prioritise practitioner relevance."""

PUBLICATIONS_PROMPT = """You are a forecasting researcher helping a data scientist stay current
with the academic literature.

Search for forecasting-related papers and publications from the past 14 days in:
{journals}

Focus on: probabilistic forecasting, neural forecasting, LLMs for time series,
supply chain optimisation, demand forecasting methods, and ensemble approaches.

Include 3-5 papers. Prioritise papers with practical forecasting relevance."""

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
# Each tool is used in phase 2 of _call_claude to force structured output.
# Claude must populate the schema — the API validates it, eliminating text JSON parsing.

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
                    },
                    "required": ["headline", "summary", "source"],
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
                        "title":    {"type": "string"},
                        "authors":  {"type": "string"},
                        "venue":    {"type": "string"},
                        "summary":  {"type": "string", "description": "2-3 sentences on contribution and practitioner relevance."},
                        "url_hint": {"type": "string", "description": "arXiv ID, DOI hint, or enough info to find the paper."},
                    },
                    "required": ["title", "authors", "venue", "summary", "url_hint"],
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


def _call_claude(system: str, user: str, output_tool: dict) -> dict:
    """
    Two-phase Claude call that guarantees structured output.

    Phase 1 — web search: Claude searches freely and writes a prose response.
    Phase 2 — post-tool-use hook: Claude is forced to call `output_tool`
              (tool_choice="tool"), so the API validates and returns a typed
              Python dict. No text JSON parsing is ever needed.
    """
    client   = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    today    = datetime.today().strftime("%B %d, %Y")
    user_msg = f"Today is {today}. {user}"

    # ── Phase 1: let Claude search and produce a free-form response ───────────
    search_response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        system=system,
        messages=[{"role": "user", "content": user_msg}],
    )

    text_blocks = [b.text for b in search_response.content if b.type == "text"]
    if not text_blocks:
        raise ValueError("No text response from Claude after web search.")
    gathered = text_blocks[-1].strip()

    # ── Phase 2: post-tool-use hook — force structured output via schema ──────
    struct_response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        tools=[output_tool],
        tool_choice={"type": "tool", "name": output_tool["name"]},
        messages=[
            {"role": "user",      "content": user_msg},
            {"role": "assistant", "content": gathered},
            {"role": "user",      "content": f"Now call {output_tool['name']} with the structured data."},
        ],
    )

    tool_blocks = [b for b in struct_response.content if b.type == "tool_use"]
    if not tool_blocks:
        raise ValueError(f"Claude did not call the {output_tool['name']} tool.")
    return tool_blocks[0].input


def fetch_news() -> dict:
    print("  → Fetching industry news...")
    return _call_claude(
        system=NEWS_PROMPT.format(topics=TOPICS),
        user="Search for this week's top supply chain and business forecasting news.",
        output_tool=NEWS_TOOL,
    )


def fetch_publications() -> dict:
    print("  → Fetching recent publications...")
    return _call_claude(
        system=PUBLICATIONS_PROMPT.format(journals=JOURNALS),
        user="Search for forecasting papers published in the past 14 days.",
        output_tool=PUBLICATIONS_TOOL,
    )


def generate_social_posts(news: dict, pubs: dict) -> dict:
    print("  → Drafting LinkedIn + X posts...")
    stories_text = "\n".join(
        f"- {s['headline']}: {s['summary']}" for s in news.get("stories", [])
    )
    papers_text = "\n".join(
        f"- {p['title']} ({p['venue']}): {p['summary']}"
        for p in pubs.get("papers", [])
    )
    return _call_claude(
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
        lines += [f"{i}. {s['headline']} ({s.get('source', '')})", s["summary"], ""]

    lines += [f"What to watch: {news.get('watch', '')}", ""]

    lines.append("RECENT PUBLICATIONS")
    lines.append("─" * 40)
    for p in pubs.get("papers", []):
        lines += [
            f"{p['title']}",
            f"{p.get('authors', '')} · {p.get('venue', '')}",
            p["summary"],
            f"Find it: {p.get('url_hint', '')}",
            ""
        ]

    lines.append("SOCIAL DRAFTS")
    lines.append("─" * 40)
    li = social.get("linkedin", {})
    lines += ["LinkedIn:", li.get("post", ""), ""]
    for i, t in enumerate(social.get("x_posts", []), 1):
        lines.append(f"X ({i}): {t.get('text', '')}")

    return "\n".join(lines)


def main():
    print("⏳  Building this week's forecasting digest...")

    news  = fetch_news()
    pubs  = fetch_publications()
    social = generate_social_posts(news, pubs)

    print(f"✅  {len(news.get('stories', []))} news stories, "
          f"{len(pubs.get('papers', []))} papers, social drafts ready.")

    print("📧  Sending email via Resend...")
    email_id = send_email(news, pubs, social)
    print(f"✅  Sent! Email ID: {email_id}")

    print("📝  Publishing to GitHub Pages...")
    publish_forecasting_post(news, pubs, social)
    print("✅  Post written. GitHub Actions will commit and deploy.")


if __name__ == "__main__":
    main()
