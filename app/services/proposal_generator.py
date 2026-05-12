from __future__ import annotations

import json
from pathlib import Path

from fpdf import FPDF

from config import Config


def proposal_pdf_path(job_id: int) -> Path:
    Config.ensure_data_dirs()
    return Config.PROPOSALS_DIR / f"proposal_{job_id}.pdf"


def write_proposal_pdf(*, subject: str, body: str, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    pdf.multi_cell(0, 6, f"Subject: {subject}\n\n{body}")
    pdf.output(str(out_path))


def dumps_proposal(subject: str, body: str) -> str:
    return json.dumps({"subject": subject, "body": body}, ensure_ascii=False)


def loads_proposal(proposal_text: str | None) -> dict | None:
    if not proposal_text:
        return None
    try:
        data = json.loads(proposal_text)
        if isinstance(data, dict) and "subject" in data and "body" in data:
            return data
    except json.JSONDecodeError:
        pass
    return None
