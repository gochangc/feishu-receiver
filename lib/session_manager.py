# -*- coding: utf-8 -*-
"""SQLite 会话管理器，支持多轮对话、多轮总结和自动总结"""
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
            # 当前会话消息表
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
            # 多轮总结表，每轮独立存储
            conn.execute("""
                CREATE TABLE IF NOT EXISTS summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    round INTEGER NOT NULL,
                    summary TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_summaries_user_id ON summaries(user_id)")
            # 用户状态表（跟踪当前活跃轮次）
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_state (
                    user_id TEXT PRIMARY KEY,
                    active_round INTEGER NOT NULL DEFAULT 0,
                    active_session_id TEXT DEFAULT ''
                )
            """)
            # 兼容旧表：为 user_state 添加 active_session_id 列
            self._migrate_user_state_table(conn)
            # 兼容旧表：如果 summaries 有 UNIQUE(user_id) 约束，迁移到新结构
            self._migrate_summaries_table(conn)

    def _migrate_summaries_table(self, conn: sqlite3.Connection) -> None:
        """迁移旧的 summaries 表结构（去除 UNIQUE 约束，添加 round 列）"""
        try:
            # 检查是否有 round 列
            columns = [row[1] for row in conn.execute("PRAGMA table_info(summaries)").fetchall()]
            if "round" in columns:
                return  # 已迁移
            # 旧表需要重建：SQLite 不支持 ALTER TABLE DROP CONSTRAINT
            conn.execute("ALTER TABLE summaries RENAME TO summaries_old")
            conn.execute("""
                CREATE TABLE summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    round INTEGER NOT NULL,
                    summary TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # 迁移旧数据，round 默认为 1
            conn.execute("INSERT INTO summaries (user_id, round, summary, updated_at) SELECT user_id, 1, summary, updated_at FROM summaries_old")
            conn.execute("DROP TABLE summaries_old")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_summaries_user_id ON summaries(user_id)")
            logger.info("summaries 表已迁移到多轮结构")
        except Exception as e:
            logger.warning(f"summaries 表迁移检查: {e}")

    def _migrate_user_state_table(self, conn: sqlite3.Connection) -> None:
        """迁移旧的 user_state 表（添加 active_session_id 列）"""
        try:
            columns = [row[1] for row in conn.execute("PRAGMA table_info(user_state)").fetchall()]
            if "active_session_id" in columns:
                return  # 已有该列
            conn.execute("ALTER TABLE user_state ADD COLUMN active_session_id TEXT DEFAULT ''")
            logger.info("user_state 表已添加 active_session_id 列")
        except Exception as e:
            logger.warning(f"user_state 表迁移检查: {e}")

    def get_session(self, user_id: str) -> list[dict[str, str]]:
        """获取用户当前会话历史"""
        self.cleanup_expired()
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT role, content FROM sessions WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                (user_id, self._max_history),
            ).fetchall()
        return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]

    def add_message(self, user_id: str, role: str, content: str) -> None:
        """添加消息到当前会话"""
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute(
                "INSERT INTO sessions (user_id, role, content) VALUES (?, ?, ?)",
                (user_id, role, content),
            )

    def clear_session(self, user_id: str) -> None:
        """清除用户当前会话、所有总结和状态"""
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM summaries WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM user_state WHERE user_id = ?", (user_id,))

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

    # ------------------------------------------------------------------ #
    #  多轮总结管理
    # ------------------------------------------------------------------ #

    def get_current_round(self, user_id: str) -> int:
        """获取用户最新轮次编号（最大 round + 1）"""
        with sqlite3.connect(str(self._db_path)) as conn:
            row = conn.execute(
                "SELECT MAX(round) FROM summaries WHERE user_id = ?", (user_id,)
            ).fetchone()
            return (row[0] or 0) + 1

    def get_active_round(self, user_id: str) -> int:
        """获取用户当前活跃的轮次（0 表示最新轮）"""
        with sqlite3.connect(str(self._db_path)) as conn:
            row = conn.execute(
                "SELECT active_round FROM user_state WHERE user_id = ?", (user_id,)
            ).fetchone()
            return row[0] if row else 0

    def set_active_round(self, user_id: str, round_num: int) -> None:
        """设置用户活跃轮次（0 = 最新一轮）"""
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute(
                "INSERT INTO user_state (user_id, active_round) VALUES (?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET active_round = ?",
                (user_id, round_num, round_num),
            )

    def get_active_summary(self, user_id: str) -> str | None:
        """获取用户当前活跃轮次的总结（active_round=0 时返回最新总结）"""
        active = self.get_active_round(user_id)
        with sqlite3.connect(str(self._db_path)) as conn:
            if active == 0:
                row = conn.execute(
                    "SELECT summary FROM summaries WHERE user_id = ? ORDER BY round DESC LIMIT 1",
                    (user_id,),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT summary FROM summaries WHERE user_id = ? AND round = ?",
                    (user_id, active),
                ).fetchone()
            return row[0] if row else None

    # ------------------------------------------------------------------ #
    #  AI 工具会话管理
    # ------------------------------------------------------------------ #

    def get_active_session_id(self, user_id: str) -> str:
        """获取用户当前关联的 AI 工具会话 ID（空字符串表示使用默认）"""
        with sqlite3.connect(str(self._db_path)) as conn:
            row = conn.execute(
                "SELECT active_session_id FROM user_state WHERE user_id = ?", (user_id,)
            ).fetchone()
            return (row[0] or "") if row else ""

    def set_active_session_id(self, user_id: str, session_id: str) -> None:
        """设置用户关联的 AI 工具会话 ID"""
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute(
                "INSERT INTO user_state (user_id, active_session_id) VALUES (?, ?) "
                "ON CONFLICT(user_id) DO UPDATE SET active_session_id = ?",
                (user_id, session_id, session_id),
            )

    def get_summary(self, user_id: str) -> str | None:
        """获取用户最新一轮的总结"""
        with sqlite3.connect(str(self._db_path)) as conn:
            row = conn.execute(
                "SELECT summary FROM summaries WHERE user_id = ? ORDER BY round DESC LIMIT 1",
                (user_id,),
            ).fetchone()
            return row[0] if row else None

    def get_round_summaries(self, user_id: str) -> list[dict]:
        """获取用户所有轮次的总结列表，按轮次倒序"""
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT round, summary, updated_at FROM summaries WHERE user_id = ? ORDER BY round DESC",
                (user_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def save_summary(self, user_id: str, summary: str, round_num: int | None = None) -> None:
        """保存指定轮次的总结"""
        if round_num is None:
            round_num = self.get_current_round(user_id)
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute(
                "INSERT INTO summaries (user_id, round, summary, updated_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
                (user_id, round_num, summary),
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
        4. 保存总结到 summaries 表（新轮次）
        5. 清除旧的会话消息

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

        # 获取已有的最新总结
        prev_summary = self.get_summary(user_id)

        # 确定本轮轮次
        current_round = self.get_current_round(user_id)

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

            # 保存总结到当前轮次
            self.save_summary(user_id, summary, current_round)
            # 清除当前会话消息
            with sqlite3.connect(str(self._db_path)) as conn:
                conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
            logger.info(f"会话已自动总结并重置 user_id={user_id} round={current_round}")
            return summary

        except Exception as e:
            logger.error(f"自动总结失败 user_id={user_id}: {e}")
            return None
