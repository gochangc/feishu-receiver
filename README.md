# Feishu Receiver

通过飞书私聊消息调用 AI 编程工具（Claude Code / Codex / OpenCode）进行自动回复的服务。

## 工作原理

```
飞书用户 → 私聊机器人 → lark-cli 监听事件 → Python 调用 AI 工具 → 自动回复
```

## 前置依赖

| 工具 | 用途 | 安装方式 |
|------|------|----------|
| `python` (≥3.10) | 运行核心服务 | `winget install python` 或 [python.org](https://python.org) |
| `lark-cli` (≥1.0.50) | 飞书事件监听与消息发送 | 见[飞书 CLI 文档](https://bytedance.larkoffice.com/wiki/ILuTww7Xcimb6GkhH0mcK2f4nS7) |
| `claude` / `codex` / `opencode` | AI 编程工具（至少安装一个） | 见各工具官方文档 |
| `curl` (仅 Linux) | 下载安装脚本 | 系统自带 |

### 飞书应用配置

在[飞书开放平台](https://open.feishu.cn/app)创建企业自建应用后，需要完成以下配置：

#### 1. 开通应用权限

| 权限 | 说明 |
|------|------|
| `im:message` | 发送消息（用于机器人回复） |
| `im:message.p2p_msg:readonly` | 读取私聊消息（用于接收用户消息） |

#### 2. 配置事件订阅

进入「事件与回调」→「事件订阅」，添加以下事件：

| 事件 | 说明 |
|------|------|
| `im.message.receive_v1` | 接收消息 v2.0（当用户发送消息时触发） |

#### 3. 启用机器人能力

进入「应用能力」→「机器人」，启用机器人能力。

#### 4. 发布应用

发布应用版本并在管理后台审批通过，然后在飞书搜索机器人名称发起私聊。

## 安装

**Linux / macOS：**

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

交互式向导会引导你完成：
- 飞书 App ID / Secret 配置
- lark-cli 初始化
- 默认 AI 工具选择（claude / codex / opencode）
- 工作目录设置
- 会话模式配置
- 日志级别设置

配置保存在 `~/.feishu-receiver/config.json`。

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

### 飞书内使用命令

在飞书私聊中发送以下命令（所有命令均以卡片形式回复）：

| 命令 | 说明 |
|------|------|
| `/help` | 显示可用命令列表 |
| `/new` | 开启新一轮会话（保留历史总结） |
| `/resume` | 查看最近会话记录，支持清空并开始新会话 |
| `/ai-tool` | 查看/切换 AI 工具（claude / codex / opencode） |
| `/ai-tool <工具名>` | 直接切换到指定工具，如 `/ai-tool codex` |
| `/switch <工具名>` | `/ai-tool` 的别名 |
| `/status` | 查看当前工具、会话消息数、是否有历史总结 |
| `/clear` | 清除当前会话历史和总结 |

直接发送消息即可调用 AI 工具回复。回复前会先提示"任务已接收，正在处理"。

## 配置文件

`~/.feishu-receiver/config.json`：

```json
{
  "feishu": {
    "app_id": "cli_xxxxxxxxxx",
    "app_secret": "xxxxxxxxxx",
    "bot_name": "我的飞书机器人"
  },
  "ai_tool": {
    "default": "claude",
    "timeout": 300
  },
  "session": {
    "enabled": true,
    "max_history": 50,
    "timeout": 3600,
    "auto_summarize": true
  },
  "workdir": "/home/user/workspace",
  "logging": {
    "level": "INFO",
    "file": "logs/feishu-receiver.log",
    "max_size_mb": 10,
    "backup_count": 5
  }
}
```

## 日志

```bash
tail -f ~/.feishu-receiver/logs/feishu-receiver.log   # 服务日志
```

## 卸载

```bash
feishu-receiver uninstall
```

配置文件和会话数据保留在 `~/.feishu-receiver/`，如需完全删除：

```bash
rm -rf ~/.feishu-receiver
```

## 常见问题

**发消息没回应**

- `feishu-receiver status` 检查服务是否运行
- `lark-cli auth status` 检查飞书认证
- 确认已开通 `im:message` 和 `im:message.p2p_msg:readonly` 权限
- 确认已配置事件订阅 `im.message.receive_v1`

**AI 工具调用超时**

编辑 `~/.feishu-receiver/config.json`，修改 `ai_tool.timeout` 值（单位：秒）。

**`feishu-receiver` 命令找不到（Windows）**

重新打开终端，或手动刷新 PATH：`$env:Path += ";$env:USERPROFILE\.feishu-receiver"`

## 许可证

MIT
