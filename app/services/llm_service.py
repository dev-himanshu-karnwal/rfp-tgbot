from __future__ import annotations

import asyncio
import json
import re

from google import genai
from google.genai import errors

from app.prompts import (
    CLASSIFIER_PROMPT,
    FALLBACK_PROMPT,
    HELP_PROMPT,
    INGEST_RFP_JSON_PROMPT,
    PROPOSAL_DRAFT_PROMPT,
    START_PROMPT,
)
from config import Config

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        if not Config.GEMINI_API_KEY:
            raise RuntimeError("API_KEY is not configured")
        _client = genai.Client(api_key=Config.GEMINI_API_KEY)
    return _client


def _extract_json_object(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z0-9]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start : end + 1])
    raise ValueError("Model did not return valid JSON")


async def generate_text(prompt: str) -> str:
    client = _get_client()

    def _stream() -> str:
        out: list[str] = []
        stream = client.models.generate_content_stream(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        for chunk in stream:
            if chunk.text:
                out.append(chunk.text)
        return "".join(out)

    try:
        return await asyncio.to_thread(_stream)
    except errors.ServerError as e:
        return f"Model is temporarily unavailable ({e}). Please try again."


async def summarize_rfp_json(cleaned_text: str) -> dict:
    raw = await generate_text(
        INGEST_RFP_JSON_PROMPT.format(rfp_content=cleaned_text[:120_000])
    )
    return _extract_json_object(raw)


async def classify_intent(content: str) -> str:
    raw = await generate_text(
        CLASSIFIER_PROMPT.format(rfp_content=content[:20_000])
    )
    m = re.search(r"CATEGORY:\s*([A-Za-z_]+)", raw, flags=re.IGNORECASE)
    if m:
        return m.group(1).upper()
    return "OTHER"


async def generate_proposal_draft_json(
    *,
    rfp_summary: str,
    rfp_excerpt: str,
    extra_instructions: str = "",
) -> dict:
    raw = await generate_text(
        PROPOSAL_DRAFT_PROMPT.format(
            rfp_summary=rfp_summary[:8000],
            rfp_excerpt=rfp_excerpt[:24_000],
            extra_instructions=extra_instructions or "(none)",
        )
    )
    return _extract_json_object(raw)


async def fallback_reply(user_message: str) -> str:
    return await generate_text(FALLBACK_PROMPT.format(user_message=user_message[:16_000]))


async def start_reply() -> str:
    return await generate_text(START_PROMPT)


async def help_reply() -> str:
    return await generate_text(HELP_PROMPT)
