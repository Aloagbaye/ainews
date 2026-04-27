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
- A closing "what to watch" sentence

Return ONLY valid JSON (no markdown fences) in this exact shape:
{{
  "intro": "...",
  "stories": [
    {{"headline": "...", "summary": "..."}},
    ...
  ],
  "watch": "..."
}}"""


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
        return json.loads(candidate)
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
