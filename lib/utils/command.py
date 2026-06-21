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
    """Windows 上解析命令的完整路径。

    Windows 的 subprocess 不能直接执行 .CMD/.BAT 文件（需要 shell=True），
    因此需要用 shutil.which 找到完整路径后传给 subprocess。
    """
    if sys.platform == "win32":
        cmd = args[0]
        # 已有后缀或绝对路径，直接返回
        if cmd.endswith(".cmd") or cmd.endswith(".exe") or cmd.endswith(".CMD") or cmd.endswith(".BAT"):
            return args
        full_path = shutil.which(cmd)
        if full_path:
            return [full_path] + args[1:]
        # 找不到时尝试加 .cmd 后缀
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
