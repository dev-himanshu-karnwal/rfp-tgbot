from __future__ import annotations

import smtplib
from email.message import EmailMessage
from pathlib import Path

from config import Config


def smtp_configured() -> bool:
    return bool(Config.SMTP_HOST and Config.SMTP_FROM)


def send_proposal_email(
    *,
    to_addr: str,
    subject: str,
    body: str,
    attachment_path: Path | None = None,
) -> None:
    if not smtp_configured():
        raise RuntimeError("SMTP is not configured (SMTP_HOST, SMTP_FROM, etc.)")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = Config.SMTP_FROM or ""
    msg["To"] = to_addr
    msg.set_content(body)

    if attachment_path and attachment_path.is_file():
        data = attachment_path.read_bytes()
        msg.add_attachment(
            data,
            maintype="application",
            subtype="pdf",
            filename=attachment_path.name,
        )

    host = Config.SMTP_HOST or ""
    with smtplib.SMTP(host, Config.SMTP_PORT, timeout=60) as smtp:
        if Config.SMTP_PORT == 587:
            smtp.starttls()
        if Config.SMTP_USER and Config.SMTP_PASSWORD:
            smtp.login(Config.SMTP_USER, Config.SMTP_PASSWORD)
        smtp.send_message(msg)
