"""
Weekly AI News Digest
Fetches AI headlines via Claude web_search, summarizes them, and sends via Resend.
"""

import os
import anthropic
import resend
from datetime import datetime
from email_template import build_html_email
from publisher import publish_post

# ── Config ──────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
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
    Two-phase Claude call that guarantees structured output.

    Phase 1 — web search: Claude searches freely and writes a prose digest.
    Phase 2 — post-tool-use hook: Claude is forced to call `submit_digest`
              (tool_choice="tool"), so the API validates and returns a typed
              Python dict. No text JSON parsing is ever needed.
    """
    client   = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    today    = datetime.today().strftime("%B %d, %Y")
    user_msg = (
        f"Today is {today}. Search for and summarize the top AI news "
        f"this week covering: {TOPICS}."
    )

    # ── Phase 1: let Claude search the web and write a free-form digest ──────
    try:
        search_response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            system=SYSTEM_PROMPT.format(topics=TOPICS),
            messages=[{"role": "user", "content": user_msg}],
        )
    except anthropic.BadRequestError as e:
        raise RuntimeError(f"Anthropic API request rejected: {e}") from e
    except anthropic.APIError as e:
        raise RuntimeError(f"Anthropic API error: {e}") from e

    text_blocks = [b.text for b in search_response.content if b.type == "text"]
    if not text_blocks:
        raise ValueError("No text response from Claude after web search.")
    gathered = text_blocks[-1].strip()
    if not gathered:
        raise ValueError("Claude returned an empty response after web search.")

    # ── Phase 2: post-tool-use hook — force structured output via schema ──────
    try:
        struct_response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            tools=[DIGEST_TOOL],
            tool_choice={"type": "tool", "name": "submit_digest"},
            messages=[
                {"role": "user",      "content": user_msg},
                {"role": "assistant", "content": gathered},
                {"role": "user",      "content": "Now call submit_digest with the structured data."},
            ],
        )
    except anthropic.APIError as e:
        raise RuntimeError(f"Anthropic API error during structured output: {e}") from e

    tool_blocks = [b for b in struct_response.content if b.type == "tool_use"]
    if not tool_blocks:
        raise ValueError("Claude did not call the submit_digest tool.")

    return normalize_digest(tool_blocks[0].input)


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
        print("⏳  Fetching this week's AI news via Claude...")
        digest = fetch_and_summarize()
        print(f"✅  Got {len(digest['stories'])} stories.")

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
