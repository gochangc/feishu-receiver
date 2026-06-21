# -*- coding: utf-8 -*-
"""Claude Code 适配器"""
from .base import AIToolAdapter


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
            "--no-session-persistence",
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
