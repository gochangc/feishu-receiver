# Feishu Receiver

通过飞书私聊消息调用 Claude Code 进行自动回复的服务。

## 功能

- 监听飞书私聊消息（`im.message.receive_v1`）
- 收到消息后在后台调用 Claude Code 处理
- 将 Claude Code 的处理结果自动回复给用户
- 支持独立进程和 systemd 两种运行模式

## 安装后目录

```
~/.feishu-receiver/
├── bin/
│   ├── feishu-receiver        # 主控脚本
│   └── feishu-receiver.bat    # Windows 入口
├── lib/
│   └── feishu-receiver.py     # 核心服务
├── logs/                      # 日志目录
│   ├── feishu-receiver.log    # 服务日志
│   └── claude-debug-*.log     # Claude 调试日志
└── config                     # 配置文件（setup 命令生成）
```

## 前置依赖

安装前请确保以下工具已安装：

- `python3` `lark-cli` `claude` `curl`

安装后运行 `feishu-receiver setup`，交互式配置飞书应用。

## 安装

**Linux / macOS / Git Bash：**

```bash
curl -fsSL https://raw.githubusercontent.com/gochangc/feishu-receiver/main/install.sh | bash
```

**Windows PowerShell：**

```powershell
irm https://raw.githubusercontent.com/gochangc/feishu-receiver/main/install.ps1 | iex
```

## 使用

安装完成后，命令 `feishu-receiver` 会加入 PATH。

### 首次配置

```bash
feishu-receiver setup
```

交互式向导会引导你完成：
1. 飞书 App ID / App Secret 配置
2. Claude Code 工作目录
3. 机器人名称
4. 调用超时时间

配置保存在 `~/.feishu-receiver/config`，可通过环境变量覆盖。

### 独立模式（不依赖 systemd）

```bash
feishu-receiver start        # 后台启动
feishu-receiver stop         # 停止服务
feishu-receiver status       # 查看状态
feishu-receiver restart      # 重启服务
feishu-receiver foreground   # 前台运行（Ctrl+C 停止）
feishu-receiver setup        # 重新配置
```

安装脚本会自动创建 systemd 服务（Linux），也可用 systemctl 管理：

```bash
systemctl --user start feishu-receiver
systemctl --user stop feishu-receiver
journalctl --user -u feishu-receiver -f
```

## 配置

配置优先级：**环境变量 > 配置文件 > 默认值**

### 配置文件

运行 `feishu-receiver setup` 交互式配置，或手动编辑 `~/.feishu-receiver/config`：

```ini
FEISHU_RECEIVER_WORKDIR=/home/user/workspace
FEISHU_RECEIVER_BOT_NAME=我的飞书机器人
FEISHU_RECEIVER_CLAUDE_TIMEOUT=300
```

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `FEISHU_RECEIVER_WORKDIR` | Claude Code 工作目录 | `/home/user/workspace` |
| `FEISHU_RECEIVER_BOT_NAME` | 机器人名称（用于过滤 @提及） | `我的飞书机器人` |
| `FEISHU_RECEIVER_CLAUDE_TIMEOUT` | Claude Code 调用超时（秒） | `300` |

临时覆盖配置：

```bash
FEISHU_RECEIVER_WORKDIR=/home/user/project feishu-receiver start
```

## 日志

所有日志在 `~/.feishu-receiver/logs/` 下：

```bash
tail -f ~/.feishu-receiver/logs/feishu-receiver.log          # 服务日志
ls ~/.feishu-receiver/logs/claude-debug-*.log                # Claude 调试日志
```

## 卸载

**Linux / macOS / Git Bash：**

```bash
curl -fsSL https://raw.githubusercontent.com/gochangc/feishu-receiver/main/uninstall.sh | bash
```

**Windows PowerShell：**

```powershell
rm -r $env:USERPROFILE\.feishu-receiver
```

## 常见问题

**发消息没回应**

- 检查服务是否运行：`feishu-receiver status`
- 检查 lark-cli 配置：`lark-cli auth status`
- 检查事件总线：`lark-cli event status`

**Claude Code 调用超时**

- 调大超时时间：`FEISHU_RECEIVER_CLAUDE_TIMEOUT=600 feishu-receiver start`

**能收到消息但不能回复**

- 确认已开通 `im:message` 权限
- 确认机器人已在会话中

## 许可证

MIT
