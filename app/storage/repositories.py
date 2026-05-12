from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any

from app.storage.db import get_connection


@dataclass
class Job:
    id: int
    telegram_message_id: int
    chat_id: int
    user_id: int
    file_path: str | None
    extracted_text: str | None
    summary: str | None
    score: float | None
    proposal_text: str | None
    email: str | None
    status: str


@dataclass
class UserSession:
    user_id: int
    current_job_id: int | None
    current_step: str | None
    pending_input: str | None


def _row_to_job(row: sqlite3.Row) -> Job:
    return Job(
        id=row["id"],
        telegram_message_id=row["telegram_message_id"],
        chat_id=row["chat_id"],
        user_id=row["user_id"],
        file_path=row["file_path"],
        extracted_text=row["extracted_text"],
        summary=row["summary"],
        score=row["score"],
        proposal_text=row["proposal_text"],
        email=row["email"],
        status=row["status"],
    )


class JobRepository:
    def create(
        self,
        *,
        telegram_message_id: int,
        chat_id: int,
        user_id: int,
        file_path: str | None,
        extracted_text: str | None,
        summary: str | None,
        score: float | None,
        email: str | None,
        status: str = "received",
    ) -> int:
        with get_connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO jobs (
                    telegram_message_id, chat_id, user_id, file_path,
                    extracted_text, summary, score, proposal_text, email, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
                """,
                (
                    telegram_message_id,
                    chat_id,
                    user_id,
                    file_path,
                    extracted_text,
                    summary,
                    score,
                    email,
                    status,
                ),
            )
            conn.commit()
            return int(cur.lastrowid)

    def get(self, job_id: int) -> Job | None:
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            return _row_to_job(row) if row else None

    def update(
        self,
        job_id: int,
        *,
        summary: str | None = None,
        score: float | None = None,
        proposal_text: str | None = None,
        email: str | None = None,
        status: str | None = None,
        file_path: str | None = None,
        extracted_text: str | None = None,
    ) -> None:
        fields: list[str] = []
        values: list[Any] = []
        mapping = {
            "summary": summary,
            "score": score,
            "proposal_text": proposal_text,
            "email": email,
            "status": status,
            "file_path": file_path,
            "extracted_text": extracted_text,
        }
        for key, val in mapping.items():
            if val is not None:
                fields.append(f"{key} = ?")
                values.append(val)
        if not fields:
            return
        values.append(job_id)
        sql = f"UPDATE jobs SET {', '.join(fields)} WHERE id = ?"
        with get_connection() as conn:
            conn.execute(sql, values)
            conn.commit()


class UserSessionRepository:
    def upsert_session(
        self,
        user_id: int,
        *,
        current_job_id: int | None,
        current_step: str | None,
        pending_input: str | None = None,
    ) -> None:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO user_sessions (user_id, current_job_id, current_step, pending_input)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    current_job_id = excluded.current_job_id,
                    current_step = excluded.current_step,
                    pending_input = excluded.pending_input
                """,
                (user_id, current_job_id, current_step, pending_input),
            )
            conn.commit()

    def get(self, user_id: int) -> UserSession | None:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM user_sessions WHERE user_id = ?", (user_id,)
            ).fetchone()
            if not row:
                return None
            return UserSession(
                user_id=row["user_id"],
                current_job_id=row["current_job_id"],
                current_step=row["current_step"],
                pending_input=row["pending_input"],
            )

    def clear_pending(self, user_id: int) -> None:
        with get_connection() as conn:
            conn.execute(
                "UPDATE user_sessions SET pending_input = NULL WHERE user_id = ?",
                (user_id,),
            )
            conn.commit()
