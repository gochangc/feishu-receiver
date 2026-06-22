# -*- coding: utf-8 -*-
"""卡片回调处理器

处理飞书交互式卡片的按钮点击回调。

使用方式:
    1. 在飞书开放平台配置卡片请求网址（Card Request URL）
    2. 启动 HTTP 服务监听回调请求
    3. 调用 CardActionHandler.handle() 处理回调

当前状态: 架构预留，待接入 HTTP 端点后启用。
"""
from __future__ import annotations

import logging
from typing import Any

from lib.adapters import ADAPTERS
from lib.card_builder import CardBuilder
from lib.session_manager import SessionManager

logger = logging.getLogger(__name__)


class CardActionHandler:
    """卡片回调处理器

    负责解析卡片按钮的 action value 并执行对应操作。
    每个 action value 应包含 {"action": "<action_name>", ...} 字段。
    """

    def __init__(self, session: SessionManager):
        self._session = session
        self._current_tool: str = "claude"
        # action_name -> handler 方法的映射
        self._handlers: dict[str, callable] = {
            "switch_tool": self._handle_switch_tool,
            "resume_new_session": self._handle_resume_new_session,
            "switch_round": self._handle_switch_round,
            "view_round": self._handle_view_round,
            "load_round": self._handle_load_round,
        }

    def set_current_tool(self, tool: str) -> None:
        """同步当前工具名称（由 MessageProcessor 调用）"""
        self._current_tool = tool

    def handle(self, action_value: dict[str, Any], sender_id: str) -> dict | str:
        """处理卡片回调

        Args:
            action_value: 按钮的 value 字段，必须包含 "action" 键
            sender_id: 触发回调的用户 open_id

        Returns:
            处理结果（卡片 dict 或文本 str）
        """
        action = action_value.get("action", "")
        handler = self._handlers.get(action)
        if not handler:
            logger.warning(f"未知的卡片回调 action: {action}")
            return f"未知操作: {action}"
        return handler(action_value, sender_id)

    # ------------------------------------------------------------------ #
    #  具体 action 处理方法
    # ------------------------------------------------------------------ #

    def _handle_switch_tool(self, value: dict, sender_id: str) -> str:
        """切换 AI 工具"""
        tool_name = value.get("tool", "")
        if tool_name in ADAPTERS:
            self._current_tool = tool_name
            logger.info(f"卡片回调切换工具: {tool_name} sender={sender_id}")
            return f"✅ 已切换到 {tool_name}"
        return f"❌ 未知工具: {tool_name}"

    def _handle_resume_new_session(self, value: dict, sender_id: str) -> str:
        """清空会话，开始新一轮"""
        self._session.clear_session(sender_id)
        logger.info(f"卡片回调清空会话 sender={sender_id}")
        return "✅ 已清空会话，开始新一轮"

    def _handle_switch_round(self, value: dict, sender_id: str) -> dict | str:
        """切换到指定轮次（0=返回最新轮）"""
        round_num = value.get("round", 0)
        self._session.set_active_round(sender_id, round_num)
        if round_num == 0:
            logger.info(f"卡片回调切回最新轮 sender={sender_id}")
        else:
            logger.info(f"卡片回调切换到第 {round_num} 轮 sender={sender_id}")

        # 重新构建 /resume 卡片返回
        history = self._session.get_session(sender_id)
        count = self._session.count_messages(sender_id)
        rounds = self._session.get_round_summaries(sender_id)
        latest_round = self._session.get_current_round(sender_id)
        active_round = self._session.get_active_round(sender_id)
        return CardBuilder.resume_card(history, count, rounds, latest_round, active_round)

    def _handle_view_round(self, value: dict, sender_id: str) -> dict | str:
        """查看指定轮次的完整总结"""
        round_num = value.get("round", 0)
        rounds = self._session.get_round_summaries(sender_id)
        for r in rounds:
            if r["round"] == round_num:
                return CardBuilder.round_detail_card(r["round"], r["summary"], r["updated_at"])
        return f"❌ 未找到第 {round_num} 轮会话"

    def _handle_load_round(self, value: dict, sender_id: str) -> dict | str:
        """加载指定轮次的总结并切换"""
        round_num = value.get("round", 0)
        self._session.set_active_round(sender_id, round_num)
        logger.info(f"卡片回调加载第 {round_num} 轮总结 sender={sender_id}")

        # 返回更新后的 /resume 卡片
        history = self._session.get_session(sender_id)
        count = self._session.count_messages(sender_id)
        rounds = self._session.get_round_summaries(sender_id)
        latest_round = self._session.get_current_round(sender_id)
        active_round = self._session.get_active_round(sender_id)
        return CardBuilder.resume_card(history, count, rounds, latest_round, active_round)
