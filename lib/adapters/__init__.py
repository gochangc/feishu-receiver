# -*- coding: utf-8 -*-
"""AI 工具适配器包"""
from .base import AIToolAdapter
from .claude import ClaudeAdapter
from .codex import CodexAdapter
from .opencode import OpenCodeAdapter

ADAPTERS = {
    "claude": ClaudeAdapter,
    "codex": CodexAdapter,
    "opencode": OpenCodeAdapter,
}

__all__ = ["AIToolAdapter", "ADAPTERS", "ClaudeAdapter", "CodexAdapter", "OpenCodeAdapter"]
