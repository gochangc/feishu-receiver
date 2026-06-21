# -*- coding: utf-8 -*-
"""SQLite 会话管理器，支持多轮对话和自动总结"""
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

# 过滤工具调用相关消息的模式（JSON 格式的工具调用、命令输出等）
_TOOL_PATTERNS = (
    '{"tool', '"tool"', '"command"', '"exit_code"', '"stdout"', '"stderr"',
    '```bash', '```sh', '```cmd', '```powershell',
)


class SessionManager:
    """会话管理器，使用 SQLite 存储会话历史"""

    def __init__(self, db_path: Path, max_history: int = 50, timeout: int = 3600):
        self._db_path = db_path
        self._max_history = max_history
        self._timeout = timeout
        self._init_db()

    def _init_db(self) -> None:
        """初始化数据库表"""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_created_at ON sessions(created_at)")
            # 会话总结表，存储每个用户的历史总结
            conn.execute("""
                CREATE TABLE IF NOT EXISTS summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL UNIQUE,
                    summary TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

    def get_session(self, user_id: str) -> list[dict[str, str]]:
        """获取用户会话历史"""
        self.cleanup_expired()
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT role, content FROM sessions WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, self._max_history),
            ).fetchall()
        return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]

    def add_message(self, user_id: str, role: str, content: str) -> None:
        """添加消息到会话历史"""
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute(
                "INSERT INTO sessions (user_id, role, content) VALUES (?, ?, ?)",
                (user_id, role, content),
            )

    def clear_session(self, user_id: str) -> None:
        """清除用户会话历史（包括总结）"""
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM summaries WHERE user_id = ?", (user_id,))

    def cleanup_expired(self) -> None:
        """清理过期会话"""
        cutoff = datetime.utcnow() - timedelta(seconds=self._timeout)
        cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute("DELETE FROM sessions WHERE created_at < ?", (cutoff_str,))

    def count_messages(self, user_id: str) -> int:
        """统计用户当前会话消息数"""
        with sqlite3.connect(str(self._db_path)) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM sessions WHERE user_id = ?", (user_id,)
            ).fetchone()
            return row[0] if row else 0

    def get_recent_messages(self, user_id: str, limit: int = 50) -> list[dict[str, str]]:
        """获取最近的消息（用于总结），按时间正序返回"""
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT role, content FROM sessions WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]

    def get_summary(self, user_id: str) -> str | None:
        """获取用户的历史总结"""
        with sqlite3.connect(str(self._db_path)) as conn:
            row = conn.execute(
                "SELECT summary FROM summaries WHERE user_id = ?", (user_id,)
            ).fetchone()
            return row[0] if row else None

    def save_summary(self, user_id: str, summary: str) -> None:
        """保存或更新用户总结"""
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute(
                "INSERT INTO summaries (user_id, summary, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP) "
                "ON CONFLICT(user_id) DO UPDATE SET summary = ?, updated_at = CURRENT_TIMESTAMP",
                (user_id, summary, summary),
            )

    def _filter_messages_for_summary(self, messages: list[dict[str, str]]) -> list[dict[str, str]]:
        """过滤消息，去除工具调用相关的上下文，只保留有意义的对话内容"""
        filtered = []
        for msg in messages:
            content = msg["content"]
            # 跳过看起来像工具调用 JSON 的消息
            content_stripped = content.strip()
            if any(content_stripped.startswith(p) for p in _TOOL_PATTERNS):
                continue
            # 跳过空消息
            if not content_stripped:
                continue
            # 截断过长的消息
            if len(content) > 500:
                content = content[:500] + "..."
            filtered.append({"role": msg["role"], "content": content})
        return filtered

    def summarize_and_reset(self, user_id: str, adapter, workdir: Path, timeout: int = 300) -> str | None:
        """当会话历史达到上限时，自动总结并重置会话。

        流程：
        1. 获取最近的会话消息
        2. 过滤工具调用上下文
        3. 调用 AI 工具生成总结
        4. 保存总结到 summaries 表
        5. 清除旧的会话消息
        6. 以总结作为新会话的起点

        返回总结文本，失败时返回 None。
        """
        # 获取最近的消息用于总结
        recent = self.get_recent_messages(user_id, self._max_history)
        if not recent:
            return None

        # 过滤工具调用上下文
        filtered = self._filter_messages_for_summary(recent)
        if not filtered:
            return None

        # 获取已有的历史总结（如果有）
        prev_summary = self.get_summary(user_id)

        # 构建总结请求
        prompt_parts = ["请简洁地总结以下对话内容，保留关键信息和上下文，以便在新对话中继续："]
        if prev_summary:
            prompt_parts.append(f"\n之前的总结：\n{prev_summary}")
        prompt_parts.append("\n最近的对话：")
        for msg in filtered:
            role = "用户" if msg["role"] == "user" else "助手"
            prompt_parts.append(f"{role}: {msg['content']}")
        prompt_parts.append("\n请用中文输出总结，控制在 500 字以内。只输出总结内容，不要加其他说明。")

        summary_prompt = "\n".join(prompt_parts)

        try:
            summary = adapter.execute(summary_prompt, workdir, timeout)
            if not summary:
                logger.warning("AI 工具返回空总结，跳过")
                return None

            # 保存总结
            self.save_summary(user_id, summary)
            # 清除旧的会话消息
            with sqlite3.connect(str(self._db_path)) as conn:
                conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
            logger.info(f"会话已自动总结并重置 user_id={user_id}")
            return summary

        except Exception as e:
            logger.error(f"自动总结失败 user_id={user_id}: {e}")
            return None
