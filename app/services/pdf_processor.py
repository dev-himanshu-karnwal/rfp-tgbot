from __future__ import annotations

import asyncio
import re
from pathlib import Path

import pdfplumber


def _safe_filename(name: str | None, fallback: str) -> str:
    base = (name or fallback).strip() or fallback
    base = Path(base).name
    base = re.sub(r"[^\w.\-]", "_", base, flags=re.UNICODE)
    return base[:200] if base else fallback


def build_stored_pdf_name(job_id: int, original_name: str | None) -> str:
    return f"{job_id}_{_safe_filename(original_name, 'document.pdf')}"


async def extract_text_from_pdf(pdf_path: str | Path) -> str:
    path = Path(pdf_path)

    def _read() -> str:
        parts: list[str] = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    parts.append(text)
        return "\n".join(parts)

    return await asyncio.to_thread(_read)
