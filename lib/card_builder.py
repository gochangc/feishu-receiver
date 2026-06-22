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

    @staticmethod
    def _button(text: str, value: dict, btn_type: str = "default") -> dict:
        """按钮元素"""
        return {
            "tag": "button",
            "text": {"tag": "plain_text", "content": text},
            "type": btn_type,
            "value": value,
        }

    @staticmethod
    def _action_row(buttons: list[dict]) -> dict:
        """按钮操作行"""
        return {"tag": "action", "actions": buttons}

    # ------------------------------------------------------------------ #
    #  业务卡片
    # ------------------------------------------------------------------ #

    @classmethod
    def help_card(cls) -> dict:
        """构建 /help 帮助卡片"""
        elements = [
            cls._text("/help        - 显示此帮助"),
            cls._text("/new         - 开启新一轮会话"),
            cls._text("/resume      - 查看最近会话记录"),
            cls._text("/ai-tool     - 查看/切换 AI 工具"),
            cls._text("/status      - 查看当前状态"),
            cls._text("/clear       - 清除会话历史"),
            cls._hr(),
            cls._text("/ai-tool 和 /resume 支持快捷操作，直接输入 /ai-tool claude 即可切换"),
        ]
        return cls._card("📖 可用命令", "indigo", elements)

    @classmethod
    def resume_card(
        cls,
        history: list[dict[str, str]],
        count: int,
        summary: str | None,
    ) -> dict:
        """构建 /resume 会话管理卡片

        Args:
            history: 最近会话列表 [{"role": ..., "content": ...}, ...]
            count: 总消息数
            summary: 历史总结文本（可能为 None）
        """
        elements: list[dict[str, Any]] = []

        # 历史总结
        if summary:
            preview = summary[:200] + ("..." if len(summary) > 200 else "")
            elements.append(cls._text(f"📝 历史总结:\n{preview}"))
            elements.append(cls._hr())

        # 会话记录
        if not history:
            elements.append(cls._text("📭 暂无会话记录"))
        else:
            elements.append(cls._text(f"📜 最近会话 (共 {count} 条):"))
            for msg in history[-5:]:
                role = "👤" if msg["role"] == "user" else "🤖"
                content = msg["content"][:80]
                if len(msg["content"]) > 80:
                    content += "..."
                elements.append(cls._text(f"{role} {content}"))

        # 操作按钮
        elements.append(cls._hr())
        elements.append(
            cls._action_row([
                cls._button(
                    "🔄 清空并开始新会话",
                    {"action": "resume_new_session"},
                    btn_type="primary",
                ),
            ])
        )

        return cls._card("💬 会话管理", "blue", elements)

    @classmethod
    def ai_tool_card(cls, current_tool: str, tools: list[str]) -> dict:
        """构建 /ai-tool 工具切换卡片

        Args:
            current_tool: 当前工具名称
            tools: 可用工具列表
        """
        buttons = []
        for name in tools:
            is_current = name == current_tool
            buttons.append(
                cls._button(
                    f"{'✅ ' if is_current else ''}{name}",
                    {"action": "switch_tool", "tool": name},
                    btn_type="primary" if is_current else "default",
                )
            )

        elements = [
            cls._text(f"当前工具: {current_tool}"),
            cls._hr(),
            cls._action_row(buttons),
        ]

        return cls._card("🔧 AI 工具切换", "purple", elements)
