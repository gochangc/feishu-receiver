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
        history: list[dict[str, str]],
        count: int,
        rounds: list[dict],
        latest_round: int,
        active_round: int,
    ) -> dict:
        """构建 /resume 会话管理卡片（以轮次切换为主）

        Args:
            history: 当前会话最近消息
            count: 当前会话消息数
            rounds: 所有轮次总结 [{"round": 1, "summary": "...", "updated_at": "..."}]
            latest_round: 最新轮次编号
            active_round: 当前活跃轮次（0=最新轮）
        """
        elements: list[dict[str, Any]] = []
        is_latest = active_round == 0 or active_round >= latest_round

        # 当前状态
        if is_latest:
            elements.append(cls._text(f"当前: 第 {latest_round} 轮（最新），{count} 条消息"))
        else:
            elements.append(cls._text(f"当前: 第 {active_round} 轮（已切换）"))

        # 轮次列表（核心内容）
        if rounds:
            elements.append(cls._hr())
            buttons = []
            for r in rounds[:8]:
                marker = "▶ " if (r["round"] == active_round or (active_round == 0 and r["round"] == latest_round)) else ""
                preview = r["summary"][:25] + ("..." if len(r["summary"]) > 25 else "")
                is_active = r["round"] == active_round or (active_round == 0 and r["round"] == latest_round)
                buttons.append(
                    cls._button(
                        f"{marker}第 {r['round']} 轮  {preview}",
                        {"action": "switch_round", "round": r["round"]},
                        btn_type="primary" if is_active else "default",
                    )
                )
            for i in range(0, len(buttons), 2):
                elements.append(cls._action_row(buttons[i:i + 2]))
        else:
            elements.append(cls._hr())
            elements.append(cls._text("暂无历史会话"))

        # 非最新轮时显示返回按钮
        if not is_latest:
            elements.append(cls._hr())
            elements.append(
                cls._action_row([
                    cls._button("↩️ 返回最新会话", {"action": "switch_round", "round": 0}, btn_type="primary"),
                ])
            )

        # 底部操作
        elements.append(cls._hr())
        elements.append(
            cls._action_row([
                cls._button("🔄 清空并开始新会话", {"action": "resume_new_session"}, btn_type="default"),
            ])
        )

        return cls._card("💬 会话切换", "blue", elements)

    @classmethod
    def round_detail_card(cls, round_num: int, summary: str, updated_at: str) -> dict:
        """构建轮次详情卡片（点击轮次按钮后显示）"""
        elements = [
            cls._text(f"📅 更新时间: {updated_at}"),
            cls._hr(),
            cls._text(summary),
            cls._hr(),
            cls._action_row([
                cls._button("📋 查看完整总结", {"action": "view_round", "round": round_num}, btn_type="default"),
                cls._button("🔄 切换到此轮", {"action": "load_round", "round": round_num}, btn_type="primary"),
            ]),
        ]
        return cls._card(f"📂 第 {round_num} 轮会话", "blue", elements)

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
