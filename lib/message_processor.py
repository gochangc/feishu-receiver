# -*- coding: utf-8 -*-
"""消息处理器，协调各组件处理飞书消息"""
import re
from pathlib import Path

from lib.adapters import ADAPTERS, AIToolAdapter
from lib.config_manager import ConfigManager
from lib.session_manager import SessionManager


class MessageProcessor:
    """消息处理器"""

    def __init__(self, config: ConfigManager, session: SessionManager):
        self._config = config
        self._session = session
        self._current_tool = config.get("ai_tool.default", "claude")

    def get_adapter(self, tool_name: str | None = None) -> AIToolAdapter:
        """获取 AI 工具适配器"""
        name = tool_name or self._current_tool
        adapter_cls = ADAPTERS.get(name)
        if not adapter_cls:
            raise ValueError(f"未知的 AI 工具: {name}")
        return adapter_cls()

    def clean_message(self, content: str, bot_name: str) -> str:
        """清理消息内容，去除 @提及"""
        text = re.sub(r"<at[^>]*>([^<]+)</at>", r"\1", content).strip()
        for prefix in (f"@{bot_name}", bot_name):
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
        return text or content.strip()

    def process_command(self, message: str, sender_id: str) -> tuple[str | None, str]:
        """处理命令，返回 (命令结果, 剩余消息)"""
        if not message.startswith("/"):
            return None, message

        parts = message.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1].strip() if len(parts) > 1 else ""

        # /help - 显示帮助
        if cmd == "/help":
            help_text = """📖 可用命令:

/help        - 显示此帮助
/new         - 开启新一轮会话
/resume      - 查看最近会话记录
/ai-tool     - 切换 AI 工具
/status      - 查看当前状态
/clear       - 清除会话历史"""
            return help_text, ""

        # /new - 开启新一轮会话（清除历史，保留总结）
        if cmd == "/new":
            self._session.clear_session(sender_id)
            return "✅ 已开启新一轮会话", ""

        # /resume - 查看最近会话记录
        if cmd == "/resume":
            history = self._session.get_session(sender_id)
            if not history:
                return "📭 暂无会话记录", ""
            lines = ["📜 最近会话记录:\n"]
            for i, msg in enumerate(history[-10:], 1):
                role = "👤 用户" if msg["role"] == "user" else "🤖 助手"
                content = msg["content"][:100]
                if len(msg["content"]) > 100:
                    content += "..."
                lines.append(f"{i}. {role}: {content}")
            count = self._session.count_messages(sender_id)
            lines.append(f"\n共 {count} 条记录")
            return "\n".join(lines), ""

        # /ai-tool - 切换 AI 工具
        if cmd == "/ai-tool":
            if not args:
                tool_list = ", ".join(ADAPTERS.keys())
                return f"🔧 当前工具: {self._current_tool}\n可用工具: {tool_list}\n用法: /ai-tool <工具名>", ""
            if args in ADAPTERS:
                self._current_tool = args
                return f"✅ 已切换到 {args}", ""
            return f"❌ 未知工具: {args}\n可用: {', '.join(ADAPTERS.keys())}", ""

        # /switch - /ai-tool 的别名
        if cmd == "/switch":
            if args and args in ADAPTERS:
                self._current_tool = args
                return f"✅ 已切换到 {args}", ""
            return f"❌ 未知工具: {args}，可用: {', '.join(ADAPTERS.keys())}", ""

        # /clear - 清除会话历史
        if cmd == "/clear":
            self._session.clear_session(sender_id)
            return "✅ 会话已清除", ""

        # /status - 查看当前状态
        if cmd == "/status":
            count = self._session.count_messages(sender_id)
            summary = self._session.get_summary(sender_id)
            lines = [
                f"🔧 当前工具: {self._current_tool}",
                f"💬 会话消息: {count} 条",
            ]
            if summary:
                lines.append(f"📝 已有历史总结")
            return "\n".join(lines), ""

        return None, message

    def process(self, content: str, sender_id: str, bot_name: str) -> str:
        """处理消息并返回响应"""
        # 清理消息
        message = self.clean_message(content, bot_name)

        # 处理命令
        cmd_result, remaining = self.process_command(message, sender_id)
        if cmd_result:
            return cmd_result

        if not remaining:
            return "消息为空"

        # 获取会话历史
        session_enabled = self._config.get("session.enabled", True)
        history = []
        if session_enabled:
            # 检查是否需要自动总结
            auto_summarize = self._config.get("session.auto_summarize", True)
            if auto_summarize:
                self._auto_summarize(sender_id)
            history = self._session.get_session(sender_id)

        # 构建提示词
        prompt = self._build_prompt(remaining, history, sender_id)

        # 调用 AI 工具
        try:
            adapter = self.get_adapter()
            workdir = Path(self._config.get("workdir", "."))
            timeout = self._config.get("ai_tool.timeout", 300)
            response = adapter.execute(prompt, workdir, timeout)
        except Exception as e:
            return f"处理失败: {e}"

        # 保存会话
        if session_enabled:
            self._session.add_message(sender_id, "user", remaining)
            self._session.add_message(sender_id, "assistant", response)

        return response

    def _auto_summarize(self, sender_id: str) -> None:
        """检查并执行自动总结：当消息数达到 max_history 时触发"""
        max_history = self._config.get("session.max_history", 50)
        count = self._session.count_messages(sender_id)
        if count < max_history:
            return

        try:
            adapter = self.get_adapter()
            workdir = Path(self._config.get("workdir", "."))
            timeout = self._config.get("ai_tool.timeout", 300)
            self._session.summarize_and_reset(sender_id, adapter, workdir, timeout)
        except Exception as e:
            # 总结失败不影响正常消息处理
            import logging
            logging.getLogger(__name__).warning(f"自动总结异常: {e}")

    def _build_prompt(self, message: str, history: list[dict], sender_id: str) -> str:
        """构建完整提示词"""
        parts = []
        parts.append(f"飞书用户（open_id: {sender_id}）发送消息：")

        # 加入历史总结（如果有）
        summary = self._session.get_summary(sender_id)
        if summary:
            parts.append(f"\n历史总结：\n{summary}")

        if history:
            parts.append("\n最近会话：")
            for msg in history[-10:]:  # 只取最近 10 条
                role = "用户" if msg["role"] == "user" else "助手"
                parts.append(f"{role}: {msg['content'][:200]}")

        parts.append(f"\n当前消息：\n{message}")
        parts.append(f"\n请用中文简洁回复。当前工作目录是 {self._config.get('workdir')}。")

        return "\n".join(parts)
