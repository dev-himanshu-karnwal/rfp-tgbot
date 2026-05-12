import sqlite3
from pathlib import Path

from config import Config


def get_connection() -> sqlite3.Connection:
    Config.ensure_data_dirs()
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    Config.ensure_data_dirs()
    with sqlite3.connect(Config.DATABASE_PATH) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_message_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                file_path TEXT,
                extracted_text TEXT,
                summary TEXT,
                score REAL,
                proposal_text TEXT,
                email TEXT,
                status TEXT NOT NULL DEFAULT 'received'
            );

            CREATE TABLE IF NOT EXISTS user_sessions (
                user_id INTEGER PRIMARY KEY,
                current_job_id INTEGER,
                current_step TEXT,
                pending_input TEXT,
                FOREIGN KEY (current_job_id) REFERENCES jobs (id)
            );

            CREATE INDEX IF NOT EXISTS idx_jobs_user ON jobs (user_id);
            CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs (status);
            """
        )
        conn.commit()
