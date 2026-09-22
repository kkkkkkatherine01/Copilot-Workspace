"""SQLite 反馈日志的读写。DB_PATH 可通过环境变量配置，本地默认当前目录，
生产环境（Railway）指向挂载的 Persistent Volume 路径，避免硬编码路径。"""
import json
import os
import sqlite3
from datetime import datetime, timezone

from models import FeedbackRequest

DB_PATH = os.environ.get("DB_PATH", "./feedback.db")


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS feedback_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            message_id TEXT NOT NULL,
            user_message TEXT NOT NULL,
            retrieved_faq_ids TEXT NOT NULL,
            confidence_score REAL NOT NULL,
            suggestion TEXT NOT NULL,
            final_reply TEXT NOT NULL,
            action TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def get_all_feedback() -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM feedback_log ORDER BY id").fetchall()
    conn.close()
    return [dict(row) for row in rows]


def insert_feedback(record: FeedbackRequest) -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        INSERT INTO feedback_log
            (conversation_id, message_id, user_message, retrieved_faq_ids,
             confidence_score, suggestion, final_reply, action, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record.conversation_id,
            record.message_id,
            record.user_message,
            json.dumps(record.retrieved_faq_ids, ensure_ascii=False),
            record.confidence_score,
            record.suggestion,
            record.final_reply,
            record.action,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    conn.close()
