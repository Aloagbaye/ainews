"""
Unified LLM client with automatic Claude -> GPT fallback.

Both providers are driven through the same two-phase pattern:
  Phase 1 - web search: the model searches freely and writes a prose response.
  Phase 2 - structured extraction: the model is forced to return output that
            validates against a JSON schema, so no hand-rolled text/JSON
            parsing is ever needed.

Anthropic Claude is the primary provider. If it errors for any reason (a
sunset/retired model, an outage, a rate limit, a missing key, etc.) the call
transparently retries on OpenAI GPT, so the weekly digests keep running
instead of failing outright.
"""

import copy
import json
import os
from typing import Tuple

import anthropic
from openai import OpenAI

# ── Config ───────────────────────────────────────────────────────────────────
# Both are overridable via env vars so a model swap never requires a code change.
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")
OPENAI_MODEL    = os.environ.get("OPENAI_MODEL", "gpt-5.5")

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
OPENAI_API_KEY    = os.environ.get("OPENAI_API_KEY")

_anthropic_client = None
_openai_client = None


class ProviderError(RuntimeError):
    """Raised when a single provider's call fails (search or structured-output phase)."""


def _get_anthropic_client() -> anthropic.Anthropic:
    global _anthropic_client
    if _anthropic_client is None:
        if not ANTHROPIC_API_KEY:
            raise ProviderError("ANTHROPIC_API_KEY is not set.")
        _anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _anthropic_client


def _get_openai_client() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        if not OPENAI_API_KEY:
            raise ProviderError("OPENAI_API_KEY is not set.")
        _openai_client = OpenAI(api_key=OPENAI_API_KEY)
    return _openai_client


def _strict_json_schema(schema: dict) -> dict:
    """
    Recursively add `additionalProperties: false` to every object node so the
    schema qualifies for OpenAI's strict Structured Outputs mode. Our tool
    schemas already mark every property as required, so no other changes
    are needed to satisfy strict mode.
    """
    schema = copy.deepcopy(schema)

    def _walk(node):
        if isinstance(node, dict):
            if node.get("type") == "object" and "properties" in node:
                node["additionalProperties"] = False
            for value in node.values():
                _walk(value)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(schema)
    return schema


def _call_anthropic(system: str, user_msg: str, output_tool: dict) -> dict:
    client = _get_anthropic_client()

    try:
        search_response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=2000,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            system=system,
            messages=[{"role": "user", "content": user_msg}],
        )
    except anthropic.APIError as e:
        raise ProviderError(f"Anthropic API error during web search: {e}") from e

    text_blocks = [b.text for b in search_response.content if b.type == "text"]
    if not text_blocks:
        raise ProviderError("No text response from Claude after web search.")
    gathered = text_blocks[-1].strip()
    if not gathered:
        raise ProviderError("Claude returned an empty response after web search.")

    try:
        struct_response = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=2000,
            tools=[output_tool],
            tool_choice={"type": "tool", "name": output_tool["name"]},
            messages=[
                {"role": "user",      "content": user_msg},
                {"role": "assistant", "content": gathered},
                {"role": "user",      "content": f"Now call {output_tool['name']} with the structured data."},
            ],
        )
    except anthropic.APIError as e:
        raise ProviderError(f"Anthropic API error during structured output: {e}") from e

    tool_blocks = [b for b in struct_response.content if b.type == "tool_use"]
    if not tool_blocks:
        raise ProviderError(f"Claude did not call the {output_tool['name']} tool.")

    return tool_blocks[0].input


def _call_openai(system: str, user_msg: str, output_tool: dict) -> dict:
    client = _get_openai_client()

    try:
        search_response = client.responses.create(
            model=OPENAI_MODEL,
            instructions=system,
            input=user_msg,
            tools=[{"type": "web_search"}],
        )
    except Exception as e:
        raise ProviderError(f"OpenAI API error during web search: {e}") from e

    gathered = (search_response.output_text or "").strip()
    if not gathered:
        raise ProviderError("OpenAI returned an empty response after web search.")

    try:
        struct_response = client.responses.create(
            model=OPENAI_MODEL,
            input=[
                {"role": "user",      "content": user_msg},
                {"role": "assistant", "content": gathered},
                {"role": "user",      "content": "Now return the structured data as JSON matching the required schema."},
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": output_tool["name"],
                    "strict": True,
                    "schema": _strict_json_schema(output_tool["input_schema"]),
                }
            },
        )
    except Exception as e:
        raise ProviderError(f"OpenAI API error during structured output: {e}") from e

    raw = (struct_response.output_text or "").strip()
    if not raw:
        raise ProviderError("OpenAI did not return structured output.")

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ProviderError(f"OpenAI returned invalid JSON: {e}") from e


def call_llm_with_search(system: str, user_msg: str, output_tool: dict) -> Tuple[dict, str]:
    """
    Two-phase "search then extract structured output" call with automatic
    Claude -> GPT fallback.

    Returns (structured_output, provider_label). The provider label (e.g.
    "Claude (claude-sonnet-5)" or "OpenAI (gpt-5.5)") lets callers attribute
    which model actually produced a given digest.
    """
    errors = []

    if ANTHROPIC_API_KEY:
        try:
            result = _call_anthropic(system, user_msg, output_tool)
            return result, f"Claude ({ANTHROPIC_MODEL})"
        except ProviderError as e:
            print(f"⚠️  Anthropic call failed, falling back to OpenAI: {e}")
            errors.append(str(e))
    else:
        errors.append("ANTHROPIC_API_KEY not set.")

    if OPENAI_API_KEY:
        try:
            result = _call_openai(system, user_msg, output_tool)
            return result, f"OpenAI ({OPENAI_MODEL})"
        except ProviderError as e:
            errors.append(str(e))
    else:
        errors.append("OPENAI_API_KEY not set.")

    raise RuntimeError(
        "Both Anthropic and OpenAI calls failed:\n" + "\n".join(f"- {e}" for e in errors)
    )
