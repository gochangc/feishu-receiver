# -*- coding: utf-8 -*-
"""可配置级别的日志管理器"""
import logging
import logging.handlers
from pathlib import Path


class Logger:
    """日志管理器，支持文件和控制台输出"""

    LEVELS = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
    }

    def __init__(
        self,
        log_file: Path,
        level: str = "INFO",
        max_bytes: int = 10 * 1024 * 1024,
        backup_count: int = 5,
    ):
        self._log_file = log_file
        self._log_file.parent.mkdir(parents=True, exist_ok=True)

        self._logger = logging.getLogger("feishu-receiver")
        self._logger.setLevel(self.LEVELS.get(level.upper(), logging.INFO))

        # 文件处理器：自动轮转，防止单文件过大
        file_handler = logging.handlers.RotatingFileHandler(
            str(log_file),
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(
            logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s")
        )
        self._logger.addHandler(file_handler)

        # 控制台处理器：实时输出到终端
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(
            logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s")
        )
        self._logger.addHandler(console_handler)

    def info(self, message: str) -> None:
        """记录 INFO 级别日志"""
        self._logger.info(message)

    def warning(self, message: str) -> None:
        """记录 WARNING 级别日志"""
        self._logger.warning(message)

    def error(self, message: str) -> None:
        """记录 ERROR 级别日志"""
        self._logger.error(message)

    def debug(self, message: str) -> None:
        """记录 DEBUG 级别日志"""
        self._logger.debug(message)

    def set_level(self, level: str) -> None:
        """动态调整日志级别"""
        self._logger.setLevel(self.LEVELS.get(level.upper(), logging.INFO))
