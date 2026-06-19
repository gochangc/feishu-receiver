#!/usr/bin/env python3
import json
import os
import re
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent.parent
LOGS_DIR = SCRIPT_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)
LOG_FILE = LOGS_DIR / "feishu-receiver.log"
CONFIG_FILE = SCRIPT_DIR / "config"

# 默认值
_defaults: dict[str, str] = {
    "FEISHU_RECEIVER_WORKDIR": "/home/user/workspace",
    "FEISHU_RECEIVER_BOT_NAME": "我的飞书机器人",
    "FEISHU_RECEIVER_CLAUDE_TIMEOUT": "300",
}


def load_config() -> dict[str, str]:
    """加载配置文件，环境变量优先于配置文件，配置文件优先于默认值。"""
    cfg: dict[str, str] = dict(_defaults)
    if CONFIG_FILE.is_file():
        for line in CONFIG_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            cfg[key.strip()] = value.strip().strip('"').strip("'")
    for key in cfg:
        env_val = os.environ.get(key)
        if env_val:
            cfg[key] = env_val
    return cfg


_config = load_config()
WORK_DIR = Path(_config["FEISHU_RECEIVER_WORKDIR"])
BOT_NAME = _config["FEISHU_RECEIVER_BOT_NAME"]
CLAUDE_TIMEOUT_SECONDS = int(_config["FEISHU_RECEIVER_CLAUDE_TIMEOUT"])


def log(message: str, level: str = "INFO") -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] [{level}] {message}"
    print(line, file=sys.stderr)
    with LOG_FILE.open("a", encoding="utf-8") as file:
        file.write(line + "\n")


def clean_message(content: str) -> str:
    text = re.sub(r"<at[^>]*>([^<]+)</at>", r"\1", content).strip()
    for prefix in (f"@{BOT_NAME}", BOT_NAME):
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
    return text or content.strip()


def _resolve_cmd(args: list[str]) -> list[str]:
    """Windows 上无扩展名的命令自动加 .cmd（lark-cli、claude 等的 npm 包装器）"""
    if sys.platform == "win32" and "/" not in args[0] and "\\" not in args[0] and "." not in args[0]:
        return [args[0] + ".cmd"] + args[1:]
    return args


def run_command(args: list[str], *, input_text: str | None = None, timeout: int = 120, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        _resolve_cmd(args),
        input=input_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        cwd=str(cwd or WORK_DIR),
    )


def run_claude(args: list[str], prompt: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    for key in (
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "ANTHROPIC_BASE_URL",
        "ANTHROPIC_MODEL",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL",
        "ANTHROPIC_DEFAULT_OPUS_MODEL",
        "ANTHROPIC_DEFAULT_SONNET_MODEL",
        "CLAUDE_CODE_SUBAGENT_MODEL",
    ):
        env.pop(key, None)
    return subprocess.run(
        _resolve_cmd(args),
        input=prompt,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=CLAUDE_TIMEOUT_SECONDS,
        cwd=str(WORK_DIR),
        start_new_session=True,
        env=env,
    )


def reply_text(message_id: str, text: str) -> bool:
    text = text.strip()
    if len(text) > 4000:
        text = text[:4000] + "...(内容截断)"
    result = run_command(
        ["lark-cli", "im", "+messages-reply", "--as", "bot", "--message-id", message_id, "--text", text],
        timeout=30,
        cwd=Path.cwd(),
    )
    if result.returncode == 0:
        log(f"回复发送成功: {message_id}")
        return True
    log(f"回复发送失败: {result.stderr[:500]}", "ERROR")
    return False


def call_claude_code(message: str, sender_id: str) -> str | None:
    prompt = f"""飞书用户（open_id: {sender_id}）发送消息：

{message}

请作为 Claude Code 智能助手用中文简洁回复。当前工作目录是 {WORK_DIR}。"""
    debug_file = LOGS_DIR / f"claude-debug-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"
    args = [
        "claude",
        "-p",
        "--permission-mode",
        "bypassPermissions",
        "--debug-file",
        str(debug_file),
        "--output-format",
        "text",
        "--no-session-persistence",
    ]
    log(f"开始调用 Claude Code，超时={CLAUDE_TIMEOUT_SECONDS}s，debug={debug_file}")
    try:
        result = run_claude(args, prompt)
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        log(f"Claude Code 调用超时: {CLAUDE_TIMEOUT_SECONDS}s stdout={stdout[:300]!r} stderr={stderr[:300]!r}", "ERROR")
        return "Claude Code 处理超时，请稍后重试或把任务拆小一点。"

    if result.returncode == 0:
        output = result.stdout.strip()
        log(f"Claude Code 返回长度: {len(output)}")
        return output or "处理完成，但没有返回内容。"
    log(f"Claude Code 调用失败: {result.stderr[:500]}", "ERROR")
    return None


def handle_message(message_id: str, message: str, sender_id: str) -> None:
    try:
        log(f"后台任务开始 message_id={message_id}")
        response = call_claude_code(message, sender_id)
        reply_text(message_id, response or "处理失败，请稍后重试。")
        log(f"后台任务完成 message_id={message_id}")
    except Exception as exc:
        log(f"后台任务异常 message_id={message_id}: {exc}", "ERROR")
        reply_text(message_id, "处理异常，请查看服务日志。")


def process_event(event: dict[str, Any]) -> None:
    if event.get("type") != "im.message.receive_v1":
        return
    message_id = event.get("message_id", "")
    content = event.get("content", "")
    sender_id = event.get("sender_id", "")
    if not message_id or not content:
        log(f"跳过无效事件: {event}", "WARN")
        return

    message = clean_message(content)
    log(f"收到消息 sender={sender_id} message_id={message_id} content={message[:120]}")
    worker = threading.Thread(target=handle_message, args=(message_id, message, sender_id), daemon=True)
    worker.start()
    log(f"后台任务已启动 message_id={message_id} thread={worker.name}")


def check_lark_config() -> bool:
    result = run_command(["lark-cli", "auth", "status"], timeout=10, cwd=Path.cwd())
    # lark-cli 在已配置但未 bind 时也返回非零，只检查是否真的未配置
    combined = (result.stdout + result.stderr).lower()
    if "not configured" in combined or "not_configured" in combined:
        if "not bound" in combined or "hermes context" in combined:
            log("lark-cli 有凭证但未绑定身份，尝试继续。可运行 lark-cli config bind 完成绑定。", "WARN")
            return True
        log("lark-cli 未配置，请先执行:", "ERROR")
        log("  lark-cli config init --app-id <AppID> --app-secret-stdin --brand feishu", "ERROR")
        return False
    return True


def main() -> None:
    log("=" * 60)
    log("飞书消息自动回复服务启动")
    log(f"机器人名称: {BOT_NAME}")
    log(f"工作目录: {WORK_DIR}")
    log("监听事件: im.message.receive_v1")
    log("=" * 60)

    if not check_lark_config():
        sys.exit(1)

    process = subprocess.Popen(
        _resolve_cmd(["lark-cli", "event", "consume", "im.message.receive_v1", "--as", "bot", "--quiet"]),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.PIPE,
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
                process_event(json.loads(line))
            except json.JSONDecodeError:
                log(f"忽略非 JSON 输出: {line[:200]}", "WARN")
            except Exception as exc:
                log(f"处理事件异常: {exc}", "ERROR")
    except KeyboardInterrupt:
        log("服务已停止")
    finally:
        process.terminate()


if __name__ == "__main__":
    main()
