"""
Weekly AI News Digest
Fetches AI headlines via web search (Claude, falling back to GPT), summarizes
them, and sends via Resend.
"""

import os
import resend
from datetime import datetime
from ai_client import call_llm_with_search
from email_template import build_html_email
from publisher import publish_post

# ── Config ──────────────────────────────────────────────────────────────────
RESEND_API_KEY    = os.environ["RESEND_API_KEY"]
FROM_EMAIL        = os.environ["FROM_EMAIL"]          # e.g. digest@yourdomain.com
TO_EMAILS         = os.environ["TO_EMAILS"].split(",") # comma-separated list
TOPICS            = os.environ.get(
    "TOPICS",
    "LLMs, AI agents, ML research, AI policy, open-source AI"
)

SYSTEM_PROMPT = """You are an expert AI industry analyst writing a concise weekly digest.
Search for the most important AI news from the past 7 days covering: {topics}.
Write a newsletter-style digest with:
- A punchy one-sentence intro
- 4-5 top stories, each with a plain-text headline and 2-3 sentence summary
- For EACH story, include at least one verification link (prefer the original source / official announcement)
- A closing "what to watch" sentence"""

# Schema-bound tool used in phase 2 to force structured output.
# Claude must populate this schema — the API validates it, eliminating all text JSON parsing.
DIGEST_TOOL: dict = {
    "name": "submit_digest",
    "description": "Submit the final weekly AI news digest in structured format.",
    "input_schema": {
        "type": "object",
        "properties": {
            "intro": {
                "type": "string",
                "description": "Punchy one-sentence intro summarising the week in AI.",
            },
            "stories": {
                "type": "array",
                "description": "4-5 top stories from the past 7 days.",
                "items": {
                    "type": "object",
                    "properties": {
                        "headline": {"type": "string"},
                        "summary": {"type": "string", "description": "2-3 sentence summary."},
                        "links": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "At least one source URL per story.",
                        },
                    },
                    "required": ["headline", "summary", "links"],
                },
            },
            "watch": {
                "type": "string",
                "description": "Closing 'what to watch' sentence.",
            },
        },
        "required": ["intro", "stories", "watch"],
    },
}

def _is_http_url(value: str) -> bool:
    if not isinstance(value, str):
        return False
    return value.startswith("http://") or value.startswith("https://")


def _fallback_verify_link(headline: str) -> str:
    # Google News search is a decent "verification" fallback when no canonical URL is returned.
    # It keeps the email actionable and ensures at least one link per story.
    from urllib.parse import quote_plus

    q = quote_plus(headline or "AI news")
    return f"https://news.google.com/search?q={q}"


def normalize_digest(digest: dict) -> dict:
    """
    Ensure a stable digest shape and at least one verification link per story.
    This guards against occasional model schema drift.
    """
    if not isinstance(digest, dict):
        raise ValueError("Digest must be a dict.")

    stories = digest.get("stories") or []
    if not isinstance(stories, list):
        stories = []

    normalized_stories = []
    for story in stories:
        if not isinstance(story, dict):
            continue
        headline = (story.get("headline") or "").strip()
        summary = (story.get("summary") or "").strip()

        links_raw = story.get("links", [])
        if isinstance(links_raw, str):
            links_raw = [links_raw]
        if not isinstance(links_raw, list):
            links_raw = []

        links = []
        for link in links_raw:
            if isinstance(link, dict):
                # Allow minor schema drift like {"url": "..."}.
                link = link.get("url")
            if _is_http_url(link):
                links.append(link)

        if not links:
            links = [_fallback_verify_link(headline)]

        normalized_stories.append(
            {
                "headline": headline,
                "summary": summary,
                "links": links,
            }
        )

    digest["stories"] = normalized_stories
    if "intro" in digest and isinstance(digest["intro"], str):
        digest["intro"] = digest["intro"].strip()
    if "watch" in digest and isinstance(digest["watch"], str):
        digest["watch"] = digest["watch"].strip()
    return digest


def fetch_and_summarize() -> dict:
    """
    Two-phase "search then extract structured output" call, tried first
    against Claude and automatically falling back to GPT if Claude errors
    out (e.g. a sunset model, outage, or rate limit).
    """
    today    = datetime.today().strftime("%B %d, %Y")
    user_msg = (
        f"Today is {today}. Search for and summarize the top AI news "
        f"this week covering: {TOPICS}."
    )

    raw_digest, provider = call_llm_with_search(
        system=SYSTEM_PROMPT.format(topics=TOPICS),
        user_msg=user_msg,
        output_tool=DIGEST_TOOL,
    )

    digest = normalize_digest(raw_digest)
    digest["provider"] = provider
    return digest


def send_email(digest: dict) -> str:
    """Format and send the digest via Resend. Returns email ID."""
    resend.api_key = RESEND_API_KEY

    today       = datetime.today().strftime("%B %d, %Y")
    subject     = f"Your Weekly AI Digest — {today}"
    html_body   = build_html_email(digest, today)
    plain_body  = build_plain_text(digest)

    params: resend.Emails.SendParams = {
        "from":    FROM_EMAIL,
        "to":      TO_EMAILS,
        "subject": subject,
        "html":    html_body,
        "text":    plain_body,
    }

    result: resend.Emails.SendResponse = resend.Emails.send(params)
    return result["id"]


def build_plain_text(digest: dict) -> str:
    """Fallback plain-text version of the digest."""
    lines = [digest["intro"], ""]
    for i, story in enumerate(digest["stories"], 1):
        lines.append(f"{i}. {story['headline']}")
        lines.append(story["summary"])
        links = story.get("links") or []
        if isinstance(links, list) and links:
            lines.append(f"Verify: {links[0]}")
        lines.append("")
    lines.append(f"What to watch: {digest['watch']}")
    return "\n".join(lines)


def main():
    try:
        print("⏳  Fetching this week's AI news...")
        digest = fetch_and_summarize()
        print(f"✅  Got {len(digest['stories'])} stories via {digest['provider']}.")

        print("📧  Sending email via Resend...")
        email_id = send_email(digest)
        print(f"✅  Sent! Email ID: {email_id}")

        print("📝  Publishing to GitHub Pages...")
        publish_post(digest)
        print("✅  Post written. GitHub Actions will commit and deploy.")
    except Exception as e:
        print(f"❌  Failed to generate/send digest: {e}")
        raise


if __name__ == "__main__":
    main()
