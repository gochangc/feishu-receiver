# -*- coding: utf-8 -*-
"""飞书消息卡片构建器

负责构建飞书交互式消息卡片（Interactive Card）。
卡片回调需要 HTTP 端点配合 card_action_handler 使用。

飞书卡片文档: https://open.feishu.cn/document/common-capabilities/message-card
"""
from __future__ import annotations

from typing import Any


class CardBuilder:
    """飞书消息卡片构建器"""

    @staticmethod
    def _card(header_title: str, template: str, elements: list[dict]) -> dict:
        """构建标准卡片结构"""
        return {
            "header": {
                "title": {"tag": "plain_text", "content": header_title},
                "template": template,
            },
            "elements": elements,
        }

    @staticmethod
    def _text(content: str) -> dict:
        """纯文本块"""
        return {"tag": "div", "text": {"tag": "plain_text", "content": content}}

    @staticmethod
    def _hr() -> dict:
        return {"tag": "hr"}

    # ------------------------------------------------------------------ #
    #  业务卡片
    # ------------------------------------------------------------------ #

    @classmethod
    def help_card(cls) -> dict:
        """构建 /help 帮助卡片"""
        elements = [
            cls._text("/help        - 显示此帮助"),
            cls._text("/new         - 开启新一轮会话"),
            cls._text("/resume      - 查看/切换 AI 工具会话"),
            cls._text("/ai-tool     - 查看/切换 AI 工具"),
            cls._text("/status      - 查看当前状态"),
            cls._text("/clear       - 清除会话历史"),
            cls._hr(),
            cls._text("快捷操作: /ai-tool claude, /resume <会话ID>, /resume off"),
        ]
        return cls._card("📖 可用命令", "indigo", elements)

    @classmethod
    def new_session_card(cls) -> dict:
        """构建 /new 新会话卡片"""
        elements = [cls._text("✅ 已开启新一轮会话，历史总结已保留。")]
        return cls._card("🔄 新会话", "green", elements)

    @classmethod
    def clear_card(cls) -> dict:
        """构建 /clear 清除会话卡片"""
        elements = [cls._text("✅ 会话已清除，所有历史记录和总结已删除。")]
        return cls._card("🗑️ 清除会话", "orange", elements)

    @classmethod
    def switch_tool_card(cls, tool_name: str) -> dict:
        """构建切换工具成功卡片"""
        elements = [cls._text(f"✅ 已切换到 {tool_name}")]
        return cls._card("🔧 切换工具", "purple", elements)

    @classmethod
    def status_card(cls, current_tool: str, count: int, has_summary: bool) -> dict:
        """构建 /status 状态卡片"""
        elements = [
            cls._text(f"🔧 当前工具: {current_tool}"),
            cls._text(f"💬 会话消息: {count} 条"),
        ]
        if has_summary:
            elements.append(cls._text("📝 已有历史总结"))
        return cls._card("📊 当前状态", "wathet", elements)

    @classmethod
    def resume_card(
        cls,
        tool_name: str,
        sessions: list[dict],
        active_session_id: str,
    ) -> dict:
        """构建 /resume 会话切换卡片（展示 AI 工具的真实会话）

        Args:
            tool_name: 当前 AI 工具名称
            sessions: 会话列表 [{"session_id": ..., "title": ..., "created_at": ..., "preview": ...}]
            active_session_id: 当前关联的会话 ID（空=默认）
        """
        elements: list[dict[str, Any]] = []

        # 当前状态
        if active_session_id:
            elements.append(cls._text(f"当前工具: {tool_name} | 已关联会话"))
        else:
            elements.append(cls._text(f"当前工具: {tool_name} | 默认模式"))

        if not sessions:
            elements.append(cls._hr())
            elements.append(cls._text("暂无历史会话记录"))
        else:
            elements.append(cls._hr())
            lines = []
            for i, s in enumerate(sessions[:8], 1):
                is_active = s["session_id"] == active_session_id
                marker = "▶ " if is_active else "  "
                sid_short = s["session_id"][:8]
                title = s["title"][:30] + ("..." if len(s["title"]) > 30 else "")
                created = s.get("created_at", "")
                lines.append(f"{marker}{i}. {title}  ({created})  ID: {sid_short}")
            elements.append(cls._text("\n".join(lines)))

            elements.append(cls._hr())
            elements.append(cls._text("输入 /resume <会话ID前缀> 切换，如: /resume bd700709"))
            if active_session_id:
                elements.append(cls._text("输入 /resume off 取消关联，回到默认模式"))

        return cls._card("💬 会话切换", "blue", elements)

    @classmethod
    def ai_tool_card(cls, current_tool: str, tools: list[str]) -> dict:
        """构建 /ai-tool 工具切换卡片

        Args:
            current_tool: 当前工具名称
            tools: 可用工具列表
        """
        lines = []
        for name in tools:
            marker = "✅ " if name == current_tool else "  "
            lines.append(f"{marker}{name}")

        elements = [
            cls._text(f"当前工具: {current_tool}"),
            cls._hr(),
            cls._text("\n".join(lines)),
            cls._hr(),
            cls._text("输入 /ai-tool <工具名> 切换，如: /ai-tool claude"),
        ]

        return cls._card("🔧 AI 工具切换", "purple", elements)
