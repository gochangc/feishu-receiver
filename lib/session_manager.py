"""SQLite 会话管理器，支持多轮对话"""
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path


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
        """清除用户会话历史"""
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))

    def cleanup_expired(self) -> None:
        """清理过期会话"""
        cutoff = datetime.utcnow() - timedelta(seconds=self._timeout)
        # 使用与 SQLite CURRENT_TIMESTAMP 一致的格式（空格分隔，无 T）
        cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute("DELETE FROM sessions WHERE created_at < ?", (cutoff_str,))
