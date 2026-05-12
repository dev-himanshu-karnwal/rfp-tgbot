from __future__ import annotations


def clamp_fit_score(value: float | int | None) -> float:
    if value is None:
        return 0.0
    try:
        x = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(10.0, x))


def format_fit_score(value: float | int | None) -> str:
    return f"{clamp_fit_score(value):.1f}/10"


def ingest_fit_score(ingest: dict) -> float:
    return clamp_fit_score(ingest.get("fit_score"))
