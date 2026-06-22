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
        }

    def set_current_tool(self, tool: str) -> None:
        """同步当前工具名称（由 MessageProcessor 调用）"""
        self._current_tool = tool

    def handle(self, action_value: dict[str, Any], sender_id: str) -> str:
        """处理卡片回调

        Args:
            action_value: 按钮的 value 字段，必须包含 "action" 键
            sender_id: 触发回调的用户 open_id

        Returns:
            处理结果文本
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
