# -*- coding: utf-8 -*-
"""OpenCode 适配器"""
from .base import AIToolAdapter


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
