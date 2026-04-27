"""
Weekly AI News Digest
Fetches AI headlines via Claude web_search, summarizes them, and sends via Resend.
"""

import os
import json
import re
import anthropic
import resend
from datetime import datetime
from email_template import build_html_email

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
- 4-5 top stories, each with a short bold headline and 2-3 sentence summary
- For EACH story, include at least one verification link (prefer the original source / official announcement)
- A closing "what to watch" sentence

Return ONLY valid JSON (no markdown fences) in this exact shape:
{{
  "intro": "...",
  "stories": [
    {{"headline": "...", "summary": "...", "links": ["https://..."]}},
    ...
  ],
  "watch": "..."
}}"""

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
    """Call Claude with web_search to get this week's AI news as structured JSON."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    today  = datetime.today().strftime("%B %d, %Y")

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            system=SYSTEM_PROMPT.format(topics=TOPICS),
            messages=[{
                "role": "user",
                "content": (
                    f"Today is {today}. Search for and summarize the top AI news "
                    f"this week covering: {TOPICS}. Return the structured JSON digest now."
                )
            }]
        )
    except anthropic.BadRequestError as e:
        # Common cause: insufficient credits. Don't continue into JSON parsing.
        raise RuntimeError(f"Anthropic API request rejected: {e}") from e
    except anthropic.APIError as e:
        raise RuntimeError(f"Anthropic API error: {e}") from e

    # Extract the last text block (Claude's final answer after tool calls)
    text_blocks = [b.text for b in response.content if b.type == "text"]
    if not text_blocks:
        raise ValueError("No text response returned from Claude.")

    raw = text_blocks[-1].strip()
    if not raw:
        raise ValueError("Claude returned an empty final answer (expected JSON).")

    # Strip accidental markdown fences
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        raw = raw.lstrip()
        if raw.lower().startswith("json"):
            raw = raw[4:].lstrip()

    # If the model wrapped JSON in extra text, try to recover the JSON object.
    candidate = raw.strip()
    if not (candidate.startswith("{") and candidate.endswith("}")):
        m = re.search(r"\{[\s\S]*\}", candidate)
        if m:
            candidate = m.group(0).strip()

    try:
        digest = json.loads(candidate)
        return normalize_digest(digest)
    except json.JSONDecodeError as e:
        snippet = candidate[:500].replace("\n", "\\n")
        raise ValueError(
            "Claude output was not valid JSON. "
            f"First 500 chars: {snippet}"
        ) from e


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
    except Exception as e:
        print(f"❌  Failed to generate/send digest: {e}")
        raise


if __name__ == "__main__":
    main()
