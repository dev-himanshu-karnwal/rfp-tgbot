from __future__ import annotations

import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.services import email_service
from app.services.llm_service import (
    classify_intent,
    fallback_reply,
    generate_proposal_draft_json,
    help_reply,
    start_reply,
    summarize_rfp_json,
)
from app.services.pdf_processor import build_stored_pdf_name, extract_text_from_pdf
from app.services.proposal_generator import (
    loads_proposal,
    proposal_pdf_path,
    write_proposal_pdf,
)
from app.services.scoring_engine import format_fit_score, ingest_fit_score
from app.storage.repositories import JobRepository, UserSessionRepository
from config import Config

_jobs = JobRepository()
_sessions = UserSessionRepository()


def split_message(message: str, chunk_size: int = 4096) -> list[str]:
    return [message[i : i + chunk_size] for i in range(0, len(message), chunk_size)]


def _parse_ingest_summary(summary: str | None) -> dict:
    if not summary:
        return {}
    try:
        data = json.loads(summary)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _format_step1_text(job) -> str:
    ing = _parse_ingest_summary(job.summary)
    title = ing.get("title") or "Not Mentioned"
    client = ing.get("client") or "Not Mentioned"
    bullets = ing.get("summary") or []
    if not isinstance(bullets, list):
        bullets = [str(bullets)]
    lines = "\n".join(f"- {b}" for b in bullets[:8])
    if not lines.strip():
        lines = "- (no summary)"
    fit = format_fit_score(job.score)
    return (
        "📄 RFP Detected\n\n"
        f"Title: {title}\n"
        f"Client: {client}\n\n"
        "Summary:\n"
        f"{lines}\n\n"
        f"Fit Score: {fit}"
    )


def _keyboard_step1(job_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Generate Proposal", callback_data=f"gp:{job_id}"),
                InlineKeyboardButton("Reject", callback_data=f"rj:{job_id}"),
            ]
        ]
    )


def _keyboard_step2(job_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Edit Prompt", callback_data=f"ep:{job_id}"),
                InlineKeyboardButton("Generate PDF", callback_data=f"pdf:{job_id}"),
            ],
            [InlineKeyboardButton("Cancel", callback_data=f"cx:{job_id}")],
        ]
    )


def _keyboard_step3(job_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Send Email", callback_data=f"se:{job_id}"),
                InlineKeyboardButton("Edit Email", callback_data=f"ee:{job_id}"),
            ],
            [InlineKeyboardButton("View PDF", callback_data=f"dl:{job_id}")],
        ]
    )


def _keyboard_confirm_send(job_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Confirm ✅", callback_data=f"cf:{job_id}"),
                InlineKeyboardButton("Cancel ❌", callback_data=f"cx:{job_id}"),
            ]
        ]
    )


def _parse_callback(data: str) -> tuple[str, int] | None:
    if ":" not in data:
        return None
    action, _, rest = data.partition(":")
    rest = rest.strip()
    if not rest.isdigit():
        return None
    return action, int(rest)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("start_command invoked by user=%s", update.effective_user and update.effective_user.id)
    if not update.message:
        return
    await update.message.reply_text("Processing your request. Please wait...")
    text = await start_reply()
    for chunk in split_message(text):
        await update.message.reply_text(chunk)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("help_command invoked by user=%s", update.effective_user and update.effective_user.id)
    if not update.message:
        return
    await update.message.reply_text("Processing your request. Please wait...")
    text = await help_reply()
    for chunk in split_message(text):
        await update.message.reply_text(chunk)


async def _ingest_and_reply(
    update: Update,
    *,
    user_id: int,
    chat_id: int,
    message_id: int,
    extracted: str,
    caption: str | None,
    temp_pdf_path: Path | None,
    original_filename: str | None,
) -> None:
    logger.info(
        "_ingest_and_reply: user=%s chat=%s message=%s filename=%s text_len=%d",
        user_id, chat_id, message_id, original_filename, len(extracted),
    )
    cleaned = extracted.strip()
    if caption:
        cleaned = f"Caption: {caption}\n\n{cleaned}"
    if len(cleaned) < 40:
        logger.warning("Extracted text too short (%d chars), aborting ingest", len(cleaned))
        await update.message.reply_text(
            "Could not extract enough text from this document. "
            "Try a clearer PDF or paste the RFP as text."
        )
        if temp_pdf_path and temp_pdf_path.is_file():
            temp_pdf_path.unlink(missing_ok=True)
        return

    logger.info("Summarising RFP text (%d chars)…", len(cleaned))
    ingest = await summarize_rfp_json(cleaned)
    score = ingest_fit_score(ingest)
    summary_json = json.dumps(ingest, ensure_ascii=False)
    raw_email = ingest.get("client_email")
    email = raw_email.strip() if isinstance(raw_email, str) else None
    logger.info("RFP summarised — score=%s email=%s", score, email)

    job_id = _jobs.create(
        telegram_message_id=message_id,
        chat_id=chat_id,
        user_id=user_id,
        file_path=None,
        extracted_text=cleaned,
        summary=summary_json,
        score=score,
        email=email,
        status="received",
    )
    logger.info("Job created: job_id=%s", job_id)

    final_path: Path | None = None
    if temp_pdf_path and temp_pdf_path.is_file():
        final_path = Config.RFPS_DIR / build_stored_pdf_name(job_id, original_filename)
        temp_pdf_path.replace(final_path)
        _jobs.update(job_id, file_path=str(final_path))

    job = _jobs.get(job_id)
    if not job:
        return

    _sessions.upsert_session(
        user_id,
        current_job_id=job_id,
        current_step="received",
        pending_input=None,
    )

    await update.message.reply_text(
        _format_step1_text(job),
        reply_markup=_keyboard_step1(job_id),
    )


async def on_private_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_user:
        return

    user_id = update.effective_user.id
    session = _sessions.get(user_id)
    logger.info(
        "on_private_message: user=%s step=%s job=%s",
        user_id,
        session and session.current_step,
        session and session.current_job_id,
    )

    if session and session.current_step == "awaiting_edit_prompt" and session.current_job_id:
        job = _jobs.get(session.current_job_id)
        if job and update.message.text:
            notes = update.message.text.strip()
            logger.info("Regenerating proposal for job=%s with edit prompt", session.current_job_id)
            await update.message.reply_text("Regenerating proposal draft…")
            draft = await generate_proposal_draft_json(
                rfp_summary=job.summary or "",
                rfp_excerpt=(job.extracted_text or "")[:24_000],
                extra_instructions=notes,
            )
            proposal_json = json.dumps(
                {"subject": str(draft.get("subject") or ""), "body": str(draft.get("body") or "")},
                ensure_ascii=False,
            )
            _jobs.update(
                session.current_job_id,
                proposal_text=proposal_json,
                status="draft_ready",
            )
            _sessions.upsert_session(
                user_id,
                current_job_id=session.current_job_id,
                current_step="draft_ready",
                pending_input=None,
            )
            job2 = _jobs.get(session.current_job_id)
            if job2:
                await update.message.reply_text(
                    _format_step2_text(job2),
                    reply_markup=_keyboard_step2(job2.id),
                )
        return

    if session and session.current_step == "awaiting_edit_email" and session.current_job_id:
        if update.message.text:
            raw = update.message.text.strip()
            m = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", raw)
            new_email = m.group(0) if m else raw
            logger.info("Email updated for job=%s to=%s", session.current_job_id, new_email)
            _jobs.update(session.current_job_id, email=new_email, status="pdf_ready")
            _sessions.upsert_session(
                user_id,
                current_job_id=session.current_job_id,
                current_step="pdf_ready",
                pending_input=None,
            )
            job = _jobs.get(session.current_job_id)
            if job:
                await update.message.reply_text(
                    _format_step3_text(job),
                    reply_markup=_keyboard_step3(job.id),
                )
        return

    if session and session.current_step == "awaiting_email_confirm":
        await update.message.reply_text(
            "Please use Confirm ✅ or Cancel ❌ on the email confirmation message."
        )
        return

    doc = update.message.document
    text = update.message.text or ""

    if doc and doc.mime_type == "application/pdf":
        logger.info("PDF document received: filename=%s size=%s", doc.file_name, doc.file_size)
        await update.message.reply_text("Processing your RFP. Please wait…")
        Config.ensure_data_dirs()
        temp = Config.RFPS_DIR / f"pending_{update.message.message_id}.pdf"
        file = await doc.get_file()
        await file.download_to_drive(str(temp))
        extracted = await extract_text_from_pdf(temp)
        await _ingest_and_reply(
            update,
            user_id=user_id,
            chat_id=update.effective_chat.id,
            message_id=update.message.message_id,
            extracted=extracted,
            caption=update.message.caption,
            temp_pdf_path=temp,
            original_filename=doc.file_name,
        )
        return

    if text.strip():
        cat = await classify_intent(text)
        logger.info("Intent classified as '%s' for user=%s", cat, user_id)
        if cat.startswith("RFP"):
            await update.message.reply_text("Processing your RFP. Please wait…")
            await _ingest_and_reply(
                update,
                user_id=user_id,
                chat_id=update.effective_chat.id,
                message_id=update.message.message_id,
                extracted=text,
                caption=None,
                temp_pdf_path=None,
                original_filename=None,
            )
            return

        await update.message.reply_text("Processing your request. Please wait…")
        reply = await fallback_reply(text)
        for chunk in split_message(reply):
            await update.message.reply_text(chunk)
        return

    await update.message.reply_text("Please send a PDF file or text RFP.")


def _format_step2_text(job) -> str:
    data = loads_proposal(job.proposal_text)
    if not data:
        return "📝 Proposal Draft Ready\n\n(no draft stored)"
    subj = data.get("subject", "")
    body = data.get("body", "")
    return f"📝 Proposal Draft Ready\n\nSubject:\n{subj}\n\nBody:\n{body}"


def _format_step3_text(job) -> str:
    data = loads_proposal(job.proposal_text)
    subj = (data or {}).get("subject", "") if data else ""
    email_line = job.email or "Not found — use Edit Email"
    return (
        "📎 Proposal PDF Ready\n\n"
        f"Email Found: {email_line}\n\n"
        f"(Subject for send: {subj})"
    )


def _format_confirm_text(job) -> str:
    return (
        "📤 Confirm Send?\n\n"
        f"To: {job.email or '(missing email)'}\n"
    )


async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data or not query.from_user:
        return

    await query.answer()
    parsed = _parse_callback(query.data)
    if not parsed:
        logger.warning("Unparseable callback data: %s", query.data)
        return

    action, job_id = parsed
    user_id = query.from_user.id
    logger.info("callback_router: action=%s job_id=%s user=%s", action, job_id, user_id)
    job = _jobs.get(job_id)
    if not job or job.user_id != user_id:
        logger.warning("Invalid callback — job not found or user mismatch (job_id=%s user=%s)", job_id, user_id)
        if query.message:
            await query.message.reply_text("This action is no longer valid.")
        return

    if action == "rj":
        logger.info("Job %s rejected by user=%s", job_id, user_id)
        _jobs.update(job_id, status="rejected")
        _sessions.upsert_session(user_id, current_job_id=None, current_step=None, pending_input=None)
        if query.message:
            await query.message.reply_text("Rejected. Send another RFP anytime.")
        return

    if action == "gp":
        logger.info("Generating proposal draft for job=%s", job_id)
        if query.message:
            await query.message.reply_text("Generating proposal draft…")
        draft = await generate_proposal_draft_json(
            rfp_summary=job.summary or "",
            rfp_excerpt=(job.extracted_text or "")[:24_000],
            extra_instructions="",
        )
        proposal_json = json.dumps(
            {"subject": str(draft.get("subject") or ""), "body": str(draft.get("body") or "")},
            ensure_ascii=False,
        )
        _jobs.update(job_id, proposal_text=proposal_json, status="draft_ready")
        job2 = _jobs.get(job_id)
        if not job2:
            return
        _sessions.upsert_session(user_id, current_job_id=job_id, current_step="draft_ready")
        await query.message.reply_text(
            _format_step2_text(job2),
            reply_markup=_keyboard_step2(job_id),
        )
        return

    if action == "pdf":
        logger.info("Generating PDF for job=%s", job_id)
        data = loads_proposal(job.proposal_text)
        if not data:
            logger.warning("No proposal draft found for job=%s", job_id)
            await query.message.reply_text("No proposal draft found. Generate a draft first.")
            return
        await query.message.reply_text("Generating PDF…")
        out = proposal_pdf_path(job_id)
        write_proposal_pdf(
            subject=str(data.get("subject") or "Proposal"),
            body=str(data.get("body") or ""),
            out_path=out,
        )
        _jobs.update(job_id, status="pdf_ready")
        _sessions.upsert_session(user_id, current_job_id=job_id, current_step="pdf_ready")
        job3 = _jobs.get(job_id)
        if job3:
            await query.message.reply_text(
                _format_step3_text(job3),
                reply_markup=_keyboard_step3(job_id),
            )
        return

    if action == "ep":
        _sessions.upsert_session(
            user_id, current_job_id=job_id, current_step="awaiting_edit_prompt"
        )
        await query.message.reply_text(
            "Send your additional instructions or edits as your next message."
        )
        return

    if action == "ee":
        _sessions.upsert_session(
            user_id, current_job_id=job_id, current_step="awaiting_edit_email"
        )
        await query.message.reply_text(
            "Send the client email address as your next message."
        )
        return

    if action == "se":
        logger.info("Send email requested for job=%s", job_id)
        if not job.email:
            logger.warning("No email on file for job=%s", job_id)
            await query.message.reply_text("No email on file. Use Edit Email first.")
            return
        _jobs.update(job_id, status="awaiting_email_confirm")
        _sessions.upsert_session(
            user_id, current_job_id=job_id, current_step="awaiting_email_confirm"
        )
        j = _jobs.get(job_id)
        if j:
            await query.message.reply_text(
                _format_confirm_text(j),
                reply_markup=_keyboard_confirm_send(job_id),
            )
        return

    if action == "cf":
        logger.info("Confirm send for job=%s to=%s", job_id, job.email)
        if job.status != "awaiting_email_confirm":
            logger.warning("Confirm called but job=%s status=%s", job_id, job.status)
            await query.message.reply_text("Nothing to confirm for this job.")
            return
        if not email_service.smtp_configured():
            logger.error("SMTP not configured — cannot send email")
            await query.message.reply_text(
                "Email is not configured. Set SMTP_HOST, SMTP_FROM, SMTP_USER, SMTP_PASSWORD."
            )
            return
        data = loads_proposal(job.proposal_text)
        subject = str((data or {}).get("subject") or "Proposal")
        body = str((data or {}).get("body") or "")
        pdf_path = proposal_pdf_path(job_id)
        try:
            email_service.send_proposal_email(
                to_addr=job.email or "",
                subject=subject,
                body=body,
                attachment_path=pdf_path if pdf_path.is_file() else None,
            )
        except Exception as e:
            logger.exception("Email send failed for job=%s: %s", job_id, e)
            await query.message.reply_text(f"Send failed: {e}")
            return
        logger.info("Email sent successfully for job=%s to=%s", job_id, job.email)
        _jobs.update(job_id, status="sent")
        _sessions.upsert_session(user_id, current_job_id=None, current_step="sent")
        await query.edit_message_text("✅ Email Sent Successfully")
        return

    if action == "cx":
        if job.status == "awaiting_email_confirm":
            _jobs.update(job_id, status="pdf_ready")
            _sessions.upsert_session(user_id, current_job_id=job_id, current_step="pdf_ready")
            await query.edit_message_text("Send cancelled.")
            return
        _sessions.upsert_session(user_id, current_job_id=job_id, current_step="draft_ready")
        await query.edit_message_text("Cancelled.")
        return

    if action == "dl":
        logger.info("Download PDF requested for job=%s", job_id)
        path = proposal_pdf_path(job_id)
        if not path.is_file():
            logger.warning("PDF file not found at %s for job=%s", path, job_id)
            await query.message.reply_text("PDF not found. Tap Generate PDF first.")
            return
        await query.message.reply_document(document=str(path), filename=path.name)
        return


def register_handlers(application: Application) -> None:
    logger.info("Registering RFP bot handlers")
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(callback_router))
    application.add_handler(
        MessageHandler(
            (filters.TEXT | filters.Document.PDF) & filters.ChatType.PRIVATE,
            on_private_message,
        )
    )
