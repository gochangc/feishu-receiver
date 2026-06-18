#!/usr/bin/env bash
set -euo pipefail

# 飞书消息接收服务安装脚本
# 用法: curl -fsSL <raw-url> | bash -s -- [--user] [--workdir /path/to/workspace]

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
            echo "用法: curl -fsSL <raw-url> | bash -s -- [--user] [--workdir /path/to/workspace]"
            echo "  --user     安装到用户目录 (~/.feishu-receiver)"
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
        echo "系统级安装需要 root 权限，请使用 sudo，或加 --user 进行用户级安装。" >&2
        exit 1
    fi
    INSTALL_DIR="/opt/feishu-receiver"
    BIN_DIR="/usr/local/bin"
    SYSTEMD_DIR="/etc/systemd/system"
else
    INSTALL_DIR="${HOME}/.feishu-receiver"
    BIN_DIR="${HOME}/.local/bin"
    SYSTEMD_DIR="${HOME}/.config/systemd/user"
    mkdir -p "$BIN_DIR" "$SYSTEMD_DIR"
fi

echo "==> 检查依赖..."
for cmd in python3 lark-cli claude curl; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "  错误: $cmd 未找到，请先安装。" >&2
        exit 1
    fi
done
echo "  依赖检查通过"

RAW_BASE="https://raw.githubusercontent.com/gochangc/feishu-receiver/main"

echo "==> 下载文件到 $INSTALL_DIR ..."
if [[ -d "$INSTALL_DIR" ]]; then
    rm -rf "$INSTALL_DIR"
fi
mkdir -p "$INSTALL_DIR"/{bin,lib,logs}
curl -fsSL "$RAW_BASE/bin/feishu-receiver" -o "$INSTALL_DIR/bin/feishu-receiver"
curl -fsSL "$RAW_BASE/lib/feishu-receiver.py" -o "$INSTALL_DIR/lib/feishu-receiver.py"

echo "==> 创建命令快捷方式..."
chmod +x "$INSTALL_DIR/lib/feishu-receiver.py" "$INSTALL_DIR/bin/feishu-receiver"
ln -sf "$INSTALL_DIR/bin/feishu-receiver" "$BIN_DIR/feishu-receiver"

echo "==> 创建 systemd 服务..."
if [[ "$INSTALL_MODE" == "system" ]]; then
    cat > "$SYSTEMD_DIR/feishu-receiver.service" <<SYSEOF
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
WorkingDirectory=$WORK_DIR
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SYSEOF
    systemctl daemon-reload
    systemctl enable feishu-receiver.service
    systemctl restart feishu-receiver.service 2>/dev/null || true
else
    cat > "$SYSTEMD_DIR/feishu-receiver.service" <<SYSEOF
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
WorkingDirectory=$WORK_DIR
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
SYSEOF
    systemctl --user daemon-reload
    systemctl --user enable feishu-receiver.service
    systemctl --user restart feishu-receiver.service 2>/dev/null || true
fi

echo ""
echo "========================================"
echo "安装完成！"
echo "========================================"
echo ""
echo "接下来请运行配置向导:"
echo ""
echo "  feishu-receiver setup"
echo ""
echo "或手动编辑配置文件: $INSTALL_DIR/config"
echo ""
echo "========================================"
