# -*- coding: utf-8 -*-
"""OpenCode 适配器"""
import sqlite3
from datetime import datetime
from pathlib import Path

from .base import AIToolAdapter, SessionInfo


class OpenCodeAdapter(AIToolAdapter):
    """OpenCode CLI 适配器"""

    def __init__(self):
        super().__init__("opencode", "opencode")

    def build_args(self, prompt: str) -> list[str]:
        """构建 OpenCode CLI 参数"""
        return ["opencode", prompt]

    def get_env_clear(self) -> list[str]:
        """无需清除的环境变量"""
        return []

    def has_session_support(self) -> bool:
        """OpenCode 不支持 CLI 恢复会话（仅 TUI 支持）"""
        return False

    def list_sessions(self, workdir: Path, limit: int = 10) -> list[SessionInfo]:
        """列出 OpenCode 历史会话

        读取 <workdir>/.opencode/opencode.db 的 session 表。
        """
        db_path = workdir / ".opencode" / "opencode.db"
        if not db_path.exists():
            return []

        try:
            with sqlite3.connect(str(db_path)) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT id, title, message_count, created_at "
                    "FROM session ORDER BY updated_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        except Exception:
            return []

        result = []
        for row in rows:
            ts = row["created_at"] or 0
            try:
                dt = datetime.fromtimestamp(ts)
                created_at = dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                created_at = ""
            title = row["title"] or row["id"][:8]
            result.append(SessionInfo(
                session_id=row["id"],
                title=title,
                created_at=created_at,
                message_count=row["message_count"] or 0,
            ))
        return result
