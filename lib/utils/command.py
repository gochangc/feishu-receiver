# -*- coding: utf-8 -*-
"""跨平台命令执行工具"""
import shutil
import subprocess
import sys
from pathlib import Path


def detect_python() -> str:
    """检测可用的 Python 命令（Windows 上 python3 可能是 Store 占位符）。

    不仅检查 PATH 中是否存在，还通过 --version 验证命令是否真正可执行。
    """
    for cmd in ["python3", "python"]:
        if not shutil.which(cmd):
            continue
        try:
            result = subprocess.run(
                [cmd, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return cmd
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            continue
    raise RuntimeError("Python not found")


def resolve_command(args: list[str]) -> list[str]:
    """Windows 上 npm 包装器需要 .cmd 后缀。

    逻辑：先检查命令本身是否可直接执行（如 python3 在 Windows 上可能是
    Store 占位符），如果可直接执行则不加后缀；否则尝试加 .cmd。
    """
    if sys.platform == "win32":
        cmd = args[0]
        # 已有后缀或命令本身可直接执行，无需修改
        if cmd.endswith(".cmd") or cmd.endswith(".exe"):
            return args
        if shutil.which(cmd):
            return args
        # npm 等 Node 包装器在 Windows 上需要 .cmd 后缀
        return [cmd + ".cmd"] + args[1:]
    return args


def run_command(
    args: list[str],
    *,
    input_text: str | None = None,
    timeout: int = 120,
    cwd: Path | None = None,
    env: dict | None = None,
) -> subprocess.CompletedProcess[str]:
    """执行命令并返回结果"""
    return subprocess.run(
        resolve_command(args),
        input=input_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        cwd=str(cwd) if cwd else None,
        env=env,
    )


def is_command_available(command: str) -> bool:
    """检查命令是否可用"""
    return shutil.which(command) is not None
