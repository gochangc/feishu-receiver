# -*- coding: utf-8 -*-
"""Codex 适配器"""
import sqlite3
from datetime import datetime
from pathlib import Path

from .base import AIToolAdapter, SessionInfo


class CodexAdapter(AIToolAdapter):
    """OpenAI Codex CLI 适配器"""

    def __init__(self):
        super().__init__("codex", "codex")

    def build_args(self, prompt: str) -> list[str]:
        """构建 Codex CLI 参数"""
        return ["codex", prompt]

    def get_env_clear(self) -> list[str]:
        """无需清除的环境变量"""
        return []

    def has_session_support(self) -> bool:
        return True

    def list_sessions(self, workdir: Path, limit: int = 10) -> list[SessionInfo]:
        """列出 Codex 历史会话

        读取 ~/.codex/state_5.sqlite 的 threads 表。
        """
        db_path = Path.home() / ".codex" / "state_5.sqlite"
        if not db_path.exists():
            return []

        try:
            with sqlite3.connect(str(db_path)) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT id, title, first_user_message, preview, created_at_ms, cwd "
                    "FROM threads WHERE archived = 0 "
                    "ORDER BY COALESCE(recency_at_ms, updated_at_ms, created_at_ms) DESC "
                    "LIMIT ?",
                    (limit,),
                ).fetchall()
        except Exception:
            return []

        result = []
        for row in rows:
            # 只保留与工作目录相关的会话
            cwd = (row["cwd"] or "").replace("\\", "/").rstrip("/")
            wd = str(workdir).replace("\\", "/").rstrip("/")
            if cwd and wd and not (wd.startswith(cwd) or cwd.startswith(wd)):
                continue

            ts_ms = row["created_at_ms"] or 0
            try:
                dt = datetime.fromtimestamp(ts_ms / 1000)
                created_at = dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                created_at = ""
            title = row["title"] or row["first_user_message"][:50] or row["id"][:8]
            preview = row["preview"] or row["first_user_message"][:100] or ""
            result.append(SessionInfo(
                session_id=row["id"],
                title=title,
                created_at=created_at,
                preview=preview,
            ))
        return result

    def build_resume_args(self, session_id: str, prompt: str) -> list[str]:
        """构建恢复会话的命令参数"""
        return ["codex", "resume", session_id, prompt]
