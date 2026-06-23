# -*- coding: utf-8 -*-
"""Claude Code 适配器"""
import json
from datetime import datetime
from pathlib import Path

from .base import AIToolAdapter, SessionInfo


class ClaudeAdapter(AIToolAdapter):
    """Claude Code CLI 适配器"""

    def __init__(self):
        super().__init__("claude", "claude")

    @property
    def use_stdin(self) -> bool:
        """Claude Code 通过 stdin 接收 prompt"""
        return True

    def build_args(self, prompt: str) -> list[str]:
        """构建 Claude Code CLI 参数"""
        return [
            "claude",
            "-p",
            "--output-format",
            "text",
        ]

    def get_env_clear(self) -> list[str]:
        """清除可能干扰 Claude Code 的环境变量"""
        return [
            "ANTHROPIC_API_KEY",
            "ANTHROPIC_AUTH_TOKEN",
            "ANTHROPIC_BASE_URL",
            "ANTHROPIC_MODEL",
            "ANTHROPIC_DEFAULT_HAIKU_MODEL",
            "ANTHROPIC_DEFAULT_OPUS_MODEL",
            "ANTHROPIC_DEFAULT_SONNET_MODEL",
            "CLAUDE_CODE_SUBAGENT_MODEL",
        ]

    def has_session_support(self) -> bool:
        return True

    def list_sessions(self, workdir: Path, limit: int = 10) -> list[SessionInfo]:
        """列出 Claude Code 历史会话

        扫描 ~/.claude/projects/<encoded-path>/*.jsonl 文件，
        读取 history.jsonl 获取元数据。
        """
        claude_dir = Path.home() / ".claude"
        history_file = claude_dir / "history.jsonl"
        if not history_file.exists():
            return []

        # 从 history.jsonl 收集 session_id -> 最后一条消息信息
        sessions: dict[str, dict] = {}
        try:
            with open(history_file, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        sid = entry.get("sessionId", "")
                        if not sid:
                            continue
                        ts = entry.get("timestamp", 0)
                        display = entry.get("display", "")
                        project = entry.get("project", "")
                        # 只保留与工作目录相关的会话
                        if project and workdir:
                            wd = str(workdir).replace("\\", "/").rstrip("/")
                            pj = project.replace("\\", "/").rstrip("/")
                            if not (wd.startswith(pj) or pj.startswith(wd)):
                                continue
                        if sid not in sessions or ts > sessions[sid]["timestamp"]:
                            sessions[sid] = {
                                "timestamp": ts,
                                "display": display,
                                "project": project,
                            }
                    except json.JSONDecodeError:
                        continue
        except Exception:
            return []

        # 按时间倒序排列
        sorted_sessions = sorted(sessions.items(), key=lambda x: x[1]["timestamp"], reverse=True)

        result = []
        for sid, info in sorted_sessions[:limit]:
            ts_ms = info["timestamp"]
            try:
                dt = datetime.fromtimestamp(ts_ms / 1000)
                created_at = dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                created_at = ""
            title = info["display"][:50] if info["display"] else sid[:8]
            result.append(SessionInfo(
                session_id=sid,
                title=title,
                created_at=created_at,
                preview=info["display"][:100],
            ))
        return result

    def build_resume_args(self, session_id: str, prompt: str) -> list[str]:
        """构建恢复会话的命令参数"""
        return [
            "claude",
            "--resume", session_id,
            "-p",
            "--output-format",
            "text",
        ]
