#!/usr/bin/env python3
"""飞书消息接收服务 - 主程序入口"""
import atexit
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

from lib.config_manager import ConfigManager
from lib.logger import Logger
from lib.message_processor import MessageProcessor
from lib.session_manager import SessionManager
from lib.utils.command import resolve_command

# 安装目录
INSTALL_DIR = Path.home() / ".feishu-receiver"
CONFIG_FILE = INSTALL_DIR / "config.json"
DB_FILE = INSTALL_DIR / "sessions.db"
PID_FILE = INSTALL_DIR / "feishu-receiver.pid"


class FeishuReceiver:
    """飞书消息接收服务"""

    def __init__(self):
        from collections import OrderedDict
        self._processed_ids: OrderedDict[str, None] = OrderedDict()
        self._lock = threading.Lock()
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

    def _kill_process_tree(self, process: subprocess.Popen) -> None:
        """杀掉 lark-cli event consume 进程及其子进程"""
        try:
            if sys.platform == "win32":
                # 先杀 cmd.exe 父进程
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)], capture_output=True, timeout=10)
                # 再杀可能残留的 lark-cli.exe 子进程
                self._kill_lark_cli_consumers()
            else:
                import os, signal
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        except Exception as e:
            self._logger.warning(f"清理进程树失败: {e}")

    def _kill_lark_cli_consumers(self) -> None:
        """启动前清理残留的 lark-cli 事件监听进程

        通过 wmic 查找 commandline 包含 'event consume' 的 lark-cli.exe 进程并杀掉，
        不影响事件总线守护进程。
        """
        if sys.platform != "win32":
            try:
                subprocess.run(["pkill", "-f", "lark-cli event consume"], capture_output=True, timeout=10)
            except Exception:
                pass
            return

        try:
            result = subprocess.run(
                ["wmic", "process", "where",
                 "name='lark-cli.exe' and commandline like '%event%consume%'",
                 "get", "processid", "/format:list"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10,
            )
            killed = 0
            for line in result.stdout.splitlines():
                line = line.strip()
                if line.startswith("ProcessId="):
                    pid = line.split("=")[1].strip()
                    if pid and pid.isdigit():
                        subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True, timeout=5)
                        killed += 1
            if killed:
                self._logger.info(f"已清理 {killed} 个残留的 lark-cli 消费进程")
        except Exception:
            pass

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
        """回复飞书文本消息（使用 markdown 格式以支持多行和富文本）"""
        if len(text) > 4000:
            text = text[:4000] + "...(内容截断)"
        try:
            result = subprocess.run(
                resolve_command(["lark-cli", "im", "+messages-reply", "--as", "bot", "--message-id", message_id, "--markdown", text]),
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
        """回复飞书卡片消息"""
        try:
            card_json = json.dumps(card, ensure_ascii=False)
            # Windows 上 | < > 被 cmd.exe 解释为管道/重定向，需转义为 JSON unicode escape
            if sys.platform == "win32":
                card_json = card_json.replace("|", "\\u007c").replace("<", "\\u003c").replace(">", "\\u003e")
            self._logger.info(f"发送卡片回复 message_id={message_id}")
            result = subprocess.run(
                resolve_command(["lark-cli", "im", "+messages-reply", "--as", "bot", "--message-id", message_id, "--msg-type", "interactive", "--content", card_json]),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
            self._logger.info(f"卡片回复 exit={result.returncode} stdout={result.stdout[:200]} stderr={result.stderr[:200]}")
            if result.returncode == 0:
                self._logger.info(f"卡片回复发送成功: {message_id}")
                return True
            self._logger.warning(f"卡片回复发送失败: {result.stderr[:300]}")
            return False
        except Exception as e:
            self._logger.warning(f"卡片回复发送异常: {e}")
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
        # 消息去重（线程安全）：lark-cli 可能同时投递重复事件
        with self._lock:
            if message_id in self._processed_ids:
                self._logger.info(f"跳过重复消息: {message_id}")
                return
            self._processed_ids[message_id] = None
            # 防止集合无限增长，移除最旧的条目
            while len(self._processed_ids) > 1000:
                self._processed_ids.popitem(last=False)
        self._logger.info(f"收到消息 sender={sender_id} message_id={message_id}")
        worker = threading.Thread(target=self.handle_message, args=(message_id, content, sender_id), daemon=True)
        worker.start()

    def _check_and_write_pid(self) -> None:
        """检查是否已有实例在运行，如果没有则写入 PID 文件"""
        current_pid = os.getpid()
        if PID_FILE.exists():
            try:
                old_pid = int(PID_FILE.read_text().strip())
                # 如果 PID 文件记录的是当前进程（PowerShell 先写 PID 再启动 Python），跳过检查
                if old_pid == current_pid:
                    pass
                # 检查进程是否仍在运行
                elif sys.platform == "win32":
                    result = subprocess.run(
                        ["tasklist", "/FI", f"PID eq {old_pid}"],
                        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5,
                    )
                    if str(old_pid) in result.stdout:
                        self._logger.error(f"服务已在运行中 (PID={old_pid})，请先停止再启动")
                        sys.exit(1)
                else:
                    try:
                        os.kill(old_pid, 0)
                        self._logger.error(f"服务已在运行中 (PID={old_pid})，请先停止再启动")
                        sys.exit(1)
                    except OSError:
                        pass  # 进程不存在
            except (ValueError, FileNotFoundError):
                pass  # PID 文件内容无效或不存在，继续启动
        # 写入当前 PID
        PID_FILE.write_text(str(current_pid))

    def _cleanup_pid(self) -> None:
        """清理 PID 文件"""
        try:
            if PID_FILE.exists():
                PID_FILE.unlink()
        except Exception:
            pass

    def _atexit_cleanup(self) -> None:
        """进程退出时清理 PID 文件和 lark-cli 消费者"""
        self._cleanup_pid()
        self._kill_lark_cli_consumers()

    def run(self) -> None:
        """运行服务"""
        # 检查并写入 PID 文件，防止重复启动
        self._check_and_write_pid()
        # 注册退出清理
        atexit.register(self._atexit_cleanup)

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
            self._cleanup_pid()
            sys.exit(1)

        # 检查 lark-cli
        if not self.check_lark_config():
            self._cleanup_pid()
            sys.exit(1)

        # 启动前清理残留的 lark-cli 事件监听进程
        self._kill_lark_cli_consumers()

        # 启动事件监听（循环重启，防止 lark-cli 意外退出）
        self._logger.info("开始监听飞书事件...")

        import time

        while True:
            # 每次重启前清理残留的消费者，防止重复
            self._kill_lark_cli_consumers()

            # 不使用 --quiet，让事件 JSON 输出到 stdout
            cmd = resolve_command(["lark-cli", "event", "consume", "im.message.receive_v1", "--as", "bot", "--timeout", "24h"])
            self._logger.info(f"启动事件监听: {' '.join(cmd)}")
            process = subprocess.Popen(
                cmd,
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
                        event = json.loads(line)
                        self.process_event(event)
                    except json.JSONDecodeError:
                        # 非 JSON 输出（如 lark-cli 状态信息），忽略
                        self._logger.debug(f"忽略非 JSON 输出: {line[:200]}")
                    except Exception as e:
                        self._logger.error(f"处理事件异常: {e}")
            except KeyboardInterrupt:
                self._logger.info("服务已停止")
                self._kill_process_tree(process)
                self._cleanup_pid()
                return
            except Exception as e:
                self._logger.error(f"事件监听异常: {e}")

            # 读取 stderr 用于调试
            if process.stderr:
                stderr_out = process.stderr.read()
                if stderr_out:
                    self._logger.warning(f"lark-cli stderr: {stderr_out[:500]}")

            self._kill_process_tree(process)
            exit_code = process.wait()
            self._logger.warning(f"事件监听进程退出 (exit={exit_code})，3 秒后重启...")
            time.sleep(3)


def main():
    receiver = FeishuReceiver()
    receiver.run()


if __name__ == "__main__":
    main()
