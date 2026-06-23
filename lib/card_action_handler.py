# -*- coding: utf-8 -*-
"""卡片回调处理器

处理飞书交互式卡片的按钮点击回调。
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable

from lib.adapters import ADAPTERS
from lib.card_builder import CardBuilder
from lib.session_manager import SessionManager

logger = logging.getLogger(__name__)


class CardActionHandler:
    """卡片回调处理器

    负责解析卡片按钮的 action value 并执行对应操作。
    每个 action value 应包含 {"action": "<action_name>", ...} 字段。
    """

    def __init__(
        self,
        session: SessionManager,
        adapter_factory: Callable[[], Any],
        get_workdir: Callable[[], Path],
        set_current_tool: Callable[[str], None],
        get_current_tool: Callable[[], str],
    ):
        self._session = session
        self._adapter_factory = adapter_factory
        self._get_workdir = get_workdir
        self._set_current_tool = set_current_tool
        self._get_current_tool = get_current_tool
        # action_name -> handler 方法的映射
        self._handlers: dict[str, Callable] = {
            "switch_tool": self._handle_switch_tool,
            "switch_session": self._handle_switch_session,
        }

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

    def _handle_switch_tool(self, value: dict, sender_id: str) -> dict | str:
        """切换 AI 工具"""
        tool_name = value.get("tool", "")
        if tool_name not in ADAPTERS:
            return f"❌ 未知工具: {tool_name}"

        self._set_current_tool(tool_name)
        logger.info(f"卡片回调切换工具: {tool_name} sender={sender_id}")

        # 切换工具后返回该工具的会话列表卡片
        try:
            adapter = self._adapter_factory()
            workdir = self._get_workdir()
            sessions = [s.to_dict() for s in adapter.list_sessions(workdir)]
            active_session_id = self._session.get_active_session_id(sender_id)
            return CardBuilder.resume_card(tool_name, sessions, active_session_id)
        except Exception as e:
            logger.warning(f"获取会话列表失败: {e}")
            return CardBuilder.switch_tool_card(tool_name)

    def _handle_switch_session(self, value: dict, sender_id: str) -> dict | str:
        """切换 AI 工具会话

        session_id 为空字符串时表示取消关联，回到默认模式。
        """
        session_id = value.get("session_id", "")
        self._session.set_active_session_id(sender_id, session_id)

        if session_id:
            logger.info(f"卡片回调关联会话: {session_id} sender={sender_id}")
        else:
            logger.info(f"卡片回调取消会话关联 sender={sender_id}")

        # 返回更新后的会话列表卡片
        try:
            tool_name = self._get_current_tool()
            adapter = self._adapter_factory()
            workdir = self._get_workdir()
            sessions = [s.to_dict() for s in adapter.list_sessions(workdir)]
            active_session_id = self._session.get_active_session_id(sender_id)
            return CardBuilder.resume_card(tool_name, sessions, active_session_id)
        except Exception as e:
            logger.warning(f"获取会话列表失败: {e}")
            return f"✅ 已{'关联会话' if session_id else '取消会话关联'}"
