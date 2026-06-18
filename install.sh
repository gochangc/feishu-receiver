#!/usr/bin/env bash
set -euo pipefail

# 飞书消息接收服务安装脚本
# 用法: ./install.sh [--user] [--workdir /path/to/workspace]

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_MODE="system"
WORK_DIR="${FEISHU_RECEIVER_WORKDIR:-/home/user/workspace}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --user)
            INSTALL_MODE="user"
            shift
            ;;
        --workdir)
            WORK_DIR="$2"
            shift 2
            ;;
        -h|--help)
            echo "用法: $0 [--user] [--workdir /path/to/workspace]"
            echo "  --user     安装到用户目录 (~/.local)，无需 sudo"
            echo "  --workdir  设置 Claude Code 的工作目录 (默认: /home/user/workspace)"
            exit 0
            ;;
        *)
            echo "未知参数: $1" >&2
            exit 1
            ;;
    esac
done

if [[ "$INSTALL_MODE" == "system" ]]; then
    if [[ "$EUID" -ne 0 ]]; then
        echo "系统级安装需要 root 权限，请使用 sudo 运行，或添加 --user 进行用户级安装。" >&2
        exit 1
    fi
    INSTALL_DIR="/opt/feishu-receiver"
    BIN_DIR="/usr/local/bin"
    SYSTEMD_DIR="/etc/systemd/system"
else
    INSTALL_DIR="${HOME}/.local/share/feishu-receiver"
    BIN_DIR="${HOME}/.local/bin"
    SYSTEMD_DIR="${HOME}/.config/systemd/user"
    mkdir -p "$BIN_DIR" "$SYSTEMD_DIR"
fi

echo "==> 检查依赖..."
for cmd in python3 lark-cli claude; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "错误: $cmd 未找到，请先安装。" >&2
        exit 1
    fi
done
echo "    依赖检查通过"

echo "==> 检查 lark-cli 配置..."
LARK_AUTH_STATUS=$(lark-cli auth status 2>&1 || true)
if echo "$LARK_AUTH_STATUS" | grep -q "not configured"; then
    echo ""
    echo "警告: lark-cli 尚未配置，服务安装后无法接收飞书消息。" >&2
    echo ""
    echo "请先执行以下命令完成配置:"
    echo "  lark-cli config init --app-id <你的AppID> --app-secret-stdin --brand feishu"
    echo ""
    echo "配置说明见下文【前置配置】部分。"
    echo ""
    if [[ -t 0 ]]; then
        read -rp "是否继续安装? (y/N) " confirm
        if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
            echo "安装已取消。"
            exit 1
        fi
    else
        echo "检测到管道模式，跳过交互确认，继续安装。"
        echo "请记得安装后完成 lark-cli 配置。"
    fi
else
    echo "    lark-cli 已配置"
fi

echo "==> 安装文件到 $INSTALL_DIR ..."
mkdir -p "$INSTALL_DIR"/{bin,lib,logs}
cp "$REPO_DIR/lib/feishu-receiver.py" "$INSTALL_DIR/lib/"
cp "$REPO_DIR/bin/feishu-receiver" "$INSTALL_DIR/bin/"
chmod +x "$INSTALL_DIR/lib/feishu-receiver.py" "$INSTALL_DIR/bin/feishu-receiver"

echo "==> 创建命令快捷方式..."
ln -sf "$INSTALL_DIR/bin/feishu-receiver" "$BIN_DIR/feishu-receiver"

echo "==> 创建 systemd 服务..."
if [[ "$INSTALL_MODE" == "system" ]]; then
    cat > "$SYSTEMD_DIR/feishu-receiver.service" <<EOF
[Unit]
Description=Feishu Message Receiver for Claude Code
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=$INSTALL_DIR/bin/feishu-receiver foreground
Restart=on-failure
RestartSec=5
Environment="FEISHU_RECEIVER_WORKDIR=$WORK_DIR"
Environment="FEISHU_RECEIVER_CLAUDE_TIMEOUT=300"
WorkingDirectory=$WORK_DIR
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    systemctl enable feishu-receiver.service
    systemctl restart feishu-receiver.service
    systemctl status feishu-receiver.service --no-pager
else
    cat > "$SYSTEMD_DIR/feishu-receiver.service" <<EOF
[Unit]
Description=Feishu Message Receiver for Claude Code (User)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=$INSTALL_DIR/bin/feishu-receiver foreground
Restart=on-failure
RestartSec=5
Environment="FEISHU_RECEIVER_WORKDIR=$WORK_DIR"
Environment="FEISHU_RECEIVER_CLAUDE_TIMEOUT=300"
WorkingDirectory=$WORK_DIR
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
EOF
    systemctl --user daemon-reload
    systemctl --user enable feishu-receiver.service
    systemctl --user restart feishu-receiver.service
    systemctl --user status feishu-receiver.service --no-pager
fi

echo ""
echo "========================================"
echo "安装完成！"
echo "========================================"
echo ""
echo "【基本信息】"
echo "  安装目录: $INSTALL_DIR"
echo "  启动命令: feishu-receiver <start|stop|status|restart|foreground>"
echo "  工作目录: $WORK_DIR"
echo "  日志目录: $INSTALL_DIR/logs/"
echo ""
echo "【配置清单：你需要自行准备】"
echo ""
echo "  以下敏感信息由你自己保管，本脚本不会存储或记录:"
echo ""
echo "  1. 飞书自建应用的 App ID"
echo "  2. 飞书自建应用的 App Secret"
echo ""
echo "  配置方式:"
echo "    lark-cli config init --app-id <你的AppID> --app-secret-stdin --brand feishu"
echo "  然后输入 App Secret 并回车。lark-cli 会将其安全存储在本地，"
echo "  不会出现在脚本、日志或环境变量中。"
echo ""
echo "【前置步骤 (必须)】"
echo ""
echo "  1. 在飞书开放平台创建自建应用"
echo "     - 访问 https://open.feishu.cn/app"
echo "     - 创建企业自建应用，获取 App ID 和 App Secret"
echo "     - 记录下这两个值，后续配置需要用到"
echo ""
echo "  2. 配置 lark-cli"
echo "     执行上面【配置清单】中的命令，完成本地认证。"
echo ""
echo "  3. 开通飞书权限"
echo "     在飞书开放平台 -> 你的应用 -> 权限管理，开通以下权限:"
echo "       - im:message                        (发送消息)"
echo "       - im:message.p2p_msg:readonly       (读取私聊消息)"
echo "     然后发布应用版本，并在飞书管理后台审批通过。"
echo ""
echo "  4. 添加机器人到会话"
echo "     在飞书搜索你的机器人名称，发起私聊。"
echo "     只有机器人加入的会话，它才能收到消息。"
echo ""
echo "  5. 验证配置"
echo "       lark-cli auth status                (查看认证状态)"
echo "       lark-cli event status               (查看事件总线状态)"
echo "       lark-cli event consume im.message.receive_v1 --as bot --max-events 1 --timeout 2m"
echo "     最后一条命令会等待接收一条消息，用于测试事件订阅是否正常。"
echo ""
if [[ "$INSTALL_MODE" == "system" ]]; then
    echo "【服务管理 (系统级)】"
    echo "  查看状态: sudo systemctl status feishu-receiver"
    echo "  启动服务: sudo systemctl start feishu-receiver"
    echo "  停止服务: sudo systemctl stop feishu-receiver"
    echo "  重启服务: sudo systemctl restart feishu-receiver"
    echo "  查看日志: sudo journalctl -u feishu-receiver -f"
else
    echo "【服务管理 (用户级)】"
    echo "  查看状态: systemctl --user status feishu-receiver"
    echo "  启动服务: systemctl --user start feishu-receiver"
    echo "  停止服务: systemctl --user stop feishu-receiver"
    echo "  重启服务: systemctl --user restart feishu-receiver"
    echo "  查看日志: journalctl --user -u feishu-receiver -f"
fi
echo ""
echo "【独立模式管理 (不依赖 systemd)】"
echo "  后台启动: feishu-receiver start"
echo "  停止服务: feishu-receiver stop"
echo "  查看状态: feishu-receiver status"
echo "  重启服务: feishu-receiver restart"
echo "  前台运行: feishu-receiver foreground"
echo ""
echo "【环境变量 (可选)】"
echo "  FEISHU_RECEIVER_WORKDIR        - Claude Code 工作目录 (默认: $WORK_DIR)"
echo "  FEISHU_RECEIVER_BOT_NAME       - 机器人名称 (默认: 我的飞书机器人)"
echo "  FEISHU_RECEIVER_CLAUDE_TIMEOUT - Claude Code 超时时间 (默认: 300秒)"
echo ""
echo "【查看服务日志】"
echo "  实时跟踪: tail -f $INSTALL_DIR/logs/feishu-receiver.log"
echo "  Claude调试: ls -la $INSTALL_DIR/logs/claude-debug-*.log"
echo ""
echo "【测试服务】"
echo "  1. 在飞书给机器人发送一条消息"
echo "  2. 观察日志: tail -f $INSTALL_DIR/logs/feishu-receiver.log"
echo "  3. 等待机器人自动回复 '任务已接收，开始处理。'"
echo ""
echo "【卸载】"
if [[ "$INSTALL_MODE" == "system" ]]; then
    echo "  sudo $REPO_DIR/uninstall.sh"
else
    echo "  $REPO_DIR/uninstall.sh --user"
fi
echo "========================================"
