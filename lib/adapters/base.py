# -*- coding: utf-8 -*-
"""AI 工具适配器基类"""
import os
import shutil
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path

from lib.utils.command import resolve_command


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

    def execute(self, prompt: str, workdir: Path, timeout: int) -> str:
        """执行 AI 工具并返回结果"""
        args = self.build_args(prompt)
        env = os.environ.copy()

        # 清除指定的环境变量，避免干扰 AI 工具的配置
        for key in self.get_env_clear():
            env.pop(key, None)

        result = subprocess.run(
            resolve_command(args),
            input=prompt,
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
