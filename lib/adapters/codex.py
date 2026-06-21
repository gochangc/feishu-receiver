# -*- coding: utf-8 -*-
"""Codex 适配器"""
from .base import AIToolAdapter


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
