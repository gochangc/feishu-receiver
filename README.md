# Feishu Receiver

通过飞书私聊消息调用 Claude Code 进行自动回复的服务。

## 功能

- 监听飞书私聊消息（`im.message.receive_v1`）
- 收到消息后自动回复"任务已接收，开始处理。"
- 在后台调用 Claude Code 处理用户消息
- 将 Claude Code 的处理结果回复给用户
- 支持后台守护进程和 systemd 两种运行模式

## 目录结构

```
feishu-receiver/
├── bin/
│   └── feishu-receiver        # 主控脚本（start/stop/status/restart/foreground）
├── lib/
│   └── feishu-receiver.py     # 核心服务脚本
├── logs/                      # 日志目录（运行时生成，已 gitignore）
├── install.sh                 # 安装脚本（Linux/macOS）
├── install.ps1                # 安装脚本（Windows PowerShell）
├── uninstall.sh               # 卸载脚本
└── README.md                  # 本文件
```

## 前置依赖

安装前请确保以下工具已安装：

- `python3`
- `lark-cli` — 飞书 CLI 工具
- `claude` — Claude Code CLI

### 飞书应用配置

1. 在[飞书开放平台](https://open.feishu.cn/app)创建企业自建应用，获取 **App ID** 和 **App Secret**
2. 配置 `lark-cli`：
   ```bash
   lark-cli config init --app-id <你的AppID> --app-secret-stdin --brand feishu
   ```
   输入 App Secret 后回车即可。
3. 在飞书开放平台给应用开通以下权限：
   - `im:message` — 发送消息
   - `im:message.p2p_msg:readonly` — 读取私聊消息
4. 发布应用版本，在飞书管理后台审批通过
5. 在飞书搜索机器人名称，发起私聊（机器人需要在会话中才能收到消息）

> 敏感信息（App ID / App Secret）由 `lark-cli` 安全存储在本地，不会出现在脚本、日志或环境变量中。

## 安装

### 一行命令安装

**Linux / macOS / Git Bash：**

```bash
curl -fsSL https://raw.githubusercontent.com/gochangc/feishu-receiver/main/install.sh | bash -s -- --user
```

系统级安装（需要 sudo）：

```bash
curl -fsSL https://raw.githubusercontent.com/gochangc/feishu-receiver/main/install.sh | sudo bash -s -- --user
```

**Windows PowerShell：**

```powershell
irm https://raw.githubusercontent.com/gochangc/feishu-receiver/main/install.ps1 | iex
```

> Windows 需要安装 Git Bash 或 WSL 来运行服务控制脚本。

### 本地安装

克隆仓库后本地运行安装脚本：

```bash
cd feishu-receiver
./install.sh --user    # 用户级安装（推荐，无需 sudo）
sudo ./install.sh      # 系统级安装
```

### 自定义工作目录

```bash
curl -fsSL https://raw.githubusercontent.com/gochangc/feishu-receiver/main/install.sh | bash -s -- --user --workdir /path/to/workspace
```

## 使用

安装完成后，命令 `feishu-receiver` 会加入 PATH。

### 独立模式（不依赖 systemd）

```bash
feishu-receiver start        # 后台启动
feishu-receiver stop         # 停止服务
feishu-receiver status       # 查看状态
feishu-receiver restart      # 重启服务
feishu-receiver foreground   # 前台运行（Ctrl+C 停止）
```

### systemd 模式

用户级安装：

```bash
systemctl --user start feishu-receiver
systemctl --user stop feishu-receiver
systemctl --user status feishu-receiver
systemctl --user restart feishu-receiver
```

系统级安装：

```bash
sudo systemctl start feishu-receiver
sudo systemctl stop feishu-receiver
sudo systemctl status feishu-receiver
sudo systemctl restart feishu-receiver
```

查看 systemd 日志：

```bash
journalctl --user -u feishu-receiver -f      # 用户级
sudo journalctl -u feishu-receiver -f        # 系统级
```

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `FEISHU_RECEIVER_WORKDIR` | Claude Code 工作目录 | `/home/user/workspace` |
| `FEISHU_RECEIVER_BOT_NAME` | 机器人名称（用于过滤 @提及） | `我的飞书机器人` |
| `FEISHU_RECEIVER_CLAUDE_TIMEOUT` | Claude Code 调用超时（秒） | `300` |

示例：

```bash
FEISHU_RECEIVER_WORKDIR=/home/user/project feishu-receiver start
```

## 日志

- 服务日志：`$INSTALL_DIR/logs/feishu-receiver.log`
- Claude 调试日志：`$INSTALL_DIR/logs/claude-debug-YYYYMMDD-HHMMSS.log`

实时查看：

```bash
tail -f ~/.local/share/feishu-receiver/logs/feishu-receiver.log
```

## 卸载

**Linux / macOS：**

```bash
./uninstall.sh --user    # 用户级
sudo ./uninstall.sh      # 系统级
```

**Windows：**

删除安装目录 `%LOCALAPPDATA%\feishu-receiver` 并从系统 PATH 中移除即可。

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
