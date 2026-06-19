# Feishu Receiver

通过飞书私聊消息调用 Claude Code 进行自动回复的服务。

## 工作原理

```
飞书用户 → 私聊机器人 → lark-cli 监听事件 → Python 调用 Claude Code → 自动回复
```

## 前置依赖

| 工具 | 用途 | 安装方式 |
|------|------|----------|
| `python` (≥3.10) | 运行核心服务 | `winget install python` 或 [python.org](https://python.org) |
| `lark-cli` (≥1.0.50) | 飞书事件监听与消息发送 | 见[飞书 CLI 文档](https://bytedance.larkoffice.com/wiki/ILuTww7Xcimb6GkhH0mcK2f4nS7) |
| `claude` | Claude Code CLI | 见[Claude Code 文档](https://docs.anthropic.com/en/docs/claude-code) |
| `curl` (仅 Linux) | 下载安装脚本 | 系统自带 |
| Git Bash 或 WSL (仅 Windows) | 运行 bash 控制脚本 | `winget install Git.Git` |

### 飞书应用准备

1. 在[飞书开放平台](https://open.feishu.cn/app)创建企业自建应用，获取 **App ID** 和 **App Secret**
2. 开通权限：`im:message`（发送消息）、`im:message.p2p_msg:readonly`（读取私聊消息）
3. 发布应用版本并在管理后台审批通过
4. 在飞书搜索机器人名称并发起私聊（机器人需在会话中才能接收消息）

## 安装

**Linux / macOS / Git Bash：**

```bash
curl -fsSL https://raw.githubusercontent.com/gochangc/feishu-receiver/main/install.sh | bash
```

**Windows PowerShell：**

```powershell
irm https://raw.githubusercontent.com/gochangc/feishu-receiver/main/install.ps1 | iex
```

安装目录：`~/.feishu-receiver`（Linux）/ `%USERPROFILE%\.feishu-receiver`（Windows）

## 使用

### 配置

```bash
feishu-receiver setup
```

交互式向导会引导你完成飞书 App ID / Secret 配置、工作目录、机器人名称和超时设置。配置保存在 `~/.feishu-receiver/config`。

> 如果 lark-cli 检测到 Hermes Agent 环境，需先将飞书凭证写入 `%LOCALAPPDATA%\hermes\.env`（`FEISHU_APP_ID` / `FEISHU_APP_SECRET`），再运行 `lark-cli config bind`。

### 命令

```bash
feishu-receiver start       # 后台启动
feishu-receiver stop        # 停止服务
feishu-receiver status      # 查看状态
feishu-receiver restart     # 重启服务
feishu-receiver foreground  # 前台运行（调试用）
feishu-receiver setup       # 重新配置
feishu-receiver uninstall   # 卸载
```

Linux 安装脚本会自动创建 systemd 用户服务，也可用 systemctl 管理：

```bash
systemctl --user start feishu-receiver
journalctl --user -u feishu-receiver -f
```

## 配置优先级

**环境变量 > 配置文件 > 默认值**

配置文件 `~/.feishu-receiver/config`：

```ini
FEISHU_RECEIVER_WORKDIR=/home/user/workspace
FEISHU_RECEIVER_BOT_NAME=我的飞书机器人
FEISHU_RECEIVER_CLAUDE_TIMEOUT=300
```

## 日志

```bash
tail -f ~/.feishu-receiver/logs/feishu-receiver.log   # 服务日志
ls ~/.feishu-receiver/logs/claude-debug-*.log         # Claude 调试日志
```

## 卸载

```bash
feishu-receiver uninstall
```

## 常见问题

**发消息没回应**

- `feishu-receiver status` 检查服务是否运行
- `lark-cli auth status` 检查飞书认证
- 确认已开通 `im:message` 和 `im:message.p2p_msg:readonly` 权限

**Claude Code 调用超时**

```bash
FEISHU_RECEIVER_CLAUDE_TIMEOUT=600 feishu-receiver start
```

**`feishu-receiver` 命令找不到（Windows）**

重新打开终端，或手动刷新 PATH：`$env:Path += ";$env:USERPROFILE\.feishu-receiver"`

## 许可证

MIT
