"""JSON 配置文件管理器"""
import copy
import json
from pathlib import Path
from typing import Any


# 默认配置
DEFAULT_CONFIG = {
    "feishu": {
        "app_id": "",
        "app_secret": "",
        "bot_name": "我的飞书机器人",
    },
    "ai_tool": {
        "default": "claude",
        "timeout": 300,
    },
    "session": {
        "enabled": True,
        "max_history": 50,
        "timeout": 3600,
    },
    "workdir": str(Path.home() / "workspace"),
    "logging": {
        "level": "INFO",
        "file": "logs/feishu-receiver.log",
        "max_size_mb": 10,
        "backup_count": 5,
    },
}


class ConfigManager:
    """配置管理器，独立管理所有配置"""

    def __init__(self, config_path: Path):
        self._path = config_path
        self._config: dict[str, Any] = {}
        self.load()

    def load(self) -> dict[str, Any]:
        """加载配置文件，不存在则使用默认配置"""
        if self._path.is_file():
            with open(self._path, "r", encoding="utf-8-sig") as f:
                self._config = json.load(f)
        else:
            self._config = copy.deepcopy(DEFAULT_CONFIG)
        return self._config

    def save(self) -> None:
        """保存配置到文件"""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._config, f, indent=2, ensure_ascii=False)

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值，支持点号分隔的嵌套键（如 'feishu.app_id'）"""
        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
            if value is None:
                return default
        return value

    def set(self, key: str, value: Any) -> None:
        """设置配置值，支持点号分隔的嵌套键"""
        keys = key.split(".")
        config = self._config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value

    def validate(self) -> list[str]:
        """验证配置有效性，返回错误列表"""
        errors = []
        if not self.get("feishu.app_id"):
            errors.append("feishu.app_id 未配置")
        if not self.get("feishu.app_secret"):
            errors.append("feishu.app_secret 未配置")
        if not self.get("workdir"):
            errors.append("workdir 未配置")
        return errors
