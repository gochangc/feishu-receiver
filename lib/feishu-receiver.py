#!/usr/bin/env python3
"""飞书消息接收服务 - 主程序入口"""
import json
import subprocess
import sys
import threading
from pathlib import Path

from lib.card_action_handler import CardActionHandler
from lib.config_manager import ConfigManager
from lib.logger import Logger
from lib.message_processor import MessageProcessor
from lib.session_manager import SessionManager
from lib.utils.command import detect_python, resolve_command

# 安装目录
INSTALL_DIR = Path.home() / ".feishu-receiver"
CONFIG_FILE = INSTALL_DIR / "config.json"
DB_FILE = INSTALL_DIR / "sessions.db"
PID_FILE = INSTALL_DIR / "feishu-receiver.pid"


class FeishuReceiver:
    """飞书消息接收服务"""

    def __init__(self):
        self._config = ConfigManager(CONFIG_FILE)
        self._logger = Logger(
            log_file=INSTALL_DIR / self._config.get("logging.file", "logs/feishu-receiver.log"),
            level=self._config.get("logging.level", "INFO"),
            max_bytes=self._config.get("logging.max_size_mb", 10) * 1024 * 1024,
            backup_count=self._config.get("logging.backup_count", 5),
        )
        self._session = SessionManager(
            db_path=DB_FILE,
            max_history=self._config.get("session.max_history", 50),
            timeout=self._config.get("session.timeout", 3600),
        )
        self._processor = MessageProcessor(self._config, self._session)
        self._card_handler = CardActionHandler(self._session)

    def check_lark_config(self) -> bool:
        """检查 lark-cli 配置"""
        try:
            result = subprocess.run(
                resolve_command(["lark-cli", "auth", "status"]),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
            )
            combined = (result.stdout + result.stderr).lower()
            if "not configured" in combined:
                self._logger.error("lark-cli 未配置，请先执行:")
                self._logger.error("  lark-cli config init --app-id <AppID> --app-secret-stdin --brand feishu")
                return False
            return True
        except Exception as e:
            self._logger.error(f"检查 lark-cli 配置失败: {e}")
            return False

    def reply_text(self, message_id: str, text: str) -> bool:
        """回复飞书文本消息"""
        if len(text) > 4000:
            text = text[:4000] + "...(内容截断)"
        try:
            result = subprocess.run(
                resolve_command(["lark-cli", "im", "+messages-reply", "--as", "bot", "--message-id", message_id, "--text", text]),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
            if result.returncode == 0:
                self._logger.info(f"回复发送成功: {message_id}")
                return True
            self._logger.error(f"回复发送失败: {result.stderr[:500]}")
            return False
        except Exception as e:
            self._logger.error(f"回复发送异常: {e}")
            return False

    def reply_card(self, message_id: str, card: dict) -> bool:
        """回复飞书卡片消息（架构预留，待 lark-cli 支持或接入 HTTP 端点后启用）"""
        try:
            card_json = json.dumps(card, ensure_ascii=False)
            result = subprocess.run(
                resolve_command(["lark-cli", "im", "+messages-reply", "--as", "bot", "--message-id", message_id, "--card", card_json]),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
            if result.returncode == 0:
                self._logger.info(f"卡片回复发送成功: {message_id}")
                return True
            # 卡片发送失败时降级为文本提示
            self._logger.warning(f"卡片回复发送失败，降级为文本: {result.stderr[:300]}")
            return False
        except Exception as e:
            self._logger.warning(f"卡片回复发送异常，降级为文本: {e}")
            return False

    def handle_message(self, message_id: str, content: str, sender_id: str) -> None:
        """处理消息（后台线程）"""
        try:
            self._logger.info(f"后台任务开始 message_id={message_id}")
            bot_name = self._config.get("feishu.bot_name", "我的飞书机器人")

            # 非命令消息先发"处理中"提示
            message = self._processor.clean_message(content, bot_name)
            if not message.startswith("/"):
                self.reply_text(message_id, "⏳ 任务已接收，正在处理中...")

            response = self._processor.process(content, sender_id, bot_name)

            # 卡片响应
            if isinstance(response, dict) and response.get("type") == "card":
                if not self.reply_card(message_id, response["card"]):
                    # 卡片发送失败，降级为文本
                    self.reply_text(message_id, "操作面板发送失败，请直接输入命令，如 /ai-tool claude")
            else:
                self.reply_text(message_id, response)

            self._logger.info(f"后台任务完成 message_id={message_id}")
        except Exception as e:
            self._logger.error(f"后台任务异常 message_id={message_id}: {e}")
            self.reply_text(message_id, "处理异常，请查看服务日志。")

    def process_event(self, event: dict) -> None:
        """处理飞书事件"""
        if event.get("type") != "im.message.receive_v1":
            return
        message_id = event.get("message_id", "")
        content = event.get("content", "")
        sender_id = event.get("sender_id", "")
        if not message_id or not content:
            self._logger.warning(f"跳过无效事件: {event}")
            return
        self._logger.info(f"收到消息 sender={sender_id} message_id={message_id}")
        worker = threading.Thread(target=self.handle_message, args=(message_id, content, sender_id), daemon=True)
        worker.start()

    def run(self) -> None:
        """运行服务"""
        self._logger.info("=" * 60)
        self._logger.info("飞书消息接收服务启动")
        self._logger.info(f"机器人名称: {self._config.get('feishu.bot_name')}")
        self._logger.info(f"工作目录: {self._config.get('workdir')}")
        self._logger.info(f"默认工具: {self._config.get('ai_tool.default')}")
        self._logger.info("监听事件: im.message.receive_v1")
        self._logger.info("=" * 60)

        # 验证配置
        errors = self._config.validate()
        if errors:
            for err in errors:
                self._logger.error(f"配置错误: {err}")
            self._logger.error("请运行: feishu-receiver setup")
            sys.exit(1)

        # 检查 lark-cli
        if not self.check_lark_config():
            sys.exit(1)

        # 启动事件监听（循环重启，防止 lark-cli 意外退出）
        self._logger.info("开始监听飞书事件...")

        import time

        while True:
            process = subprocess.Popen(
                resolve_command(["lark-cli", "event", "consume", "im.message.receive_v1", "--as", "bot", "--quiet", "--timeout", "24h"]),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            try:
                assert process.stdout is not None
                for line in process.stdout:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        self.process_event(json.loads(line))
                    except json.JSONDecodeError:
                        self._logger.warning(f"忽略非 JSON 输出: {line[:200]}")
                    except Exception as e:
                        self._logger.error(f"处理事件异常: {e}")
            except KeyboardInterrupt:
                self._logger.info("服务已停止")
                process.terminate()
                return
            except Exception as e:
                self._logger.error(f"事件监听异常: {e}")

            process.terminate()
            self._logger.warning("事件监听进程退出，3 秒后重启...")
            time.sleep(3)


def main():
    receiver = FeishuReceiver()
    receiver.run()


if __name__ == "__main__":
    main()
