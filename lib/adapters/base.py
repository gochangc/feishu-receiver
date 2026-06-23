# -*- coding: utf-8 -*-
"""AI 工具适配器基类"""
import os
import shutil
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path

from lib.utils.command import resolve_command


class SessionInfo:
    """会话信息"""

    def __init__(self, session_id: str, title: str, created_at: str,
                 message_count: int = 0, preview: str = ""):
        self.session_id = session_id
        self.title = title
        self.created_at = created_at
        self.message_count = message_count
        self.preview = preview

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "title": self.title,
            "created_at": self.created_at,
            "message_count": self.message_count,
            "preview": self.preview,
        }


class AIToolAdapter(ABC):
    """AI 工具适配器基类，定义统一接口"""

    def __init__(self, name: str, command: str):
        self._name = name
        self._command = command

    def get_name(self) -> str:
        """获取工具名称"""
        return self._name

    def is_available(self) -> bool:
        """检查工具是否可用"""
        return shutil.which(self._command) is not None

    @abstractmethod
    def build_args(self, prompt: str) -> list[str]:
        """构建命令参数"""
        ...

    @abstractmethod
    def get_env_clear(self) -> list[str]:
        """获取需要清除的环境变量列表"""
        ...

    @property
    def use_stdin(self) -> bool:
        """是否通过 stdin 传递 prompt（默认 False，子类可覆盖）"""
        return False

    def has_session_support(self) -> bool:
        """是否支持会话管理（子类可覆盖）"""
        return False

    def list_sessions(self, workdir: Path, limit: int = 10) -> list[SessionInfo]:
        """列出历史会话（子类可覆盖）"""
        return []

    def build_resume_args(self, session_id: str, prompt: str) -> list[str]:
        """构建恢复会话的命令参数（子类可覆盖）"""
        return []

    def execute(self, prompt: str, workdir: Path, timeout: int) -> str:
        """执行 AI 工具并返回结果"""
        return self._execute_internal(None, prompt, workdir, timeout)

    def execute_with_session(self, session_id: str, prompt: str, workdir: Path, timeout: int) -> str:
        """在指定会话上下文中执行 AI 工具"""
        return self._execute_internal(session_id, prompt, workdir, timeout)

    def _execute_internal(self, session_id: str | None, prompt: str, workdir: Path, timeout: int) -> str:
        """内部执行方法，支持可选的会话恢复"""
        if session_id:
            args = self.build_resume_args(session_id, prompt)
        else:
            args = self.build_args(prompt)
        env = os.environ.copy()

        # 清除指定的环境变量，避免干扰 AI 工具的配置
        for key in self.get_env_clear():
            env.pop(key, None)

        result = subprocess.run(
            resolve_command(args),
            input=prompt if self.use_stdin else None,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=str(workdir),
            start_new_session=True,
            env=env,
        )

        if result.returncode == 0:
            return result.stdout.strip()
        raise RuntimeError(f"{self._name} 调用失败: {result.stderr[:500]}")
