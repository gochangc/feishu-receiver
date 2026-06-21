#!/usr/bin/env bash
set -euo pipefail

# 飞书消息接收服务安装脚本
# 用法: curl -fsSL <raw-url> | bash

INSTALL_DIR="${HOME}/.feishu-receiver"
BIN_DIR="${HOME}/.local/bin"
SYSTEMD_DIR="${HOME}/.config/systemd/user"
RAW_BASE="https://raw.githubusercontent.com/gochangc/feishu-receiver/main"

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)
            echo "用法: curl -fsSL <raw-url> | bash"
            exit 0
            ;;
        *)
            echo "未知参数: $1" >&2
            exit 1
            ;;
    esac
done

mkdir -p "$BIN_DIR" "$SYSTEMD_DIR"

echo "==> 检查依赖..."
for cmd in python3 lark-cli curl; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "  错误: $cmd 未找到，请先安装。" >&2
        exit 1
    fi
done
echo "  依赖检查通过"

echo "==> 下载文件到 $INSTALL_DIR ..."
if [[ -d "$INSTALL_DIR" ]]; then
    rm -rf "$INSTALL_DIR"
fi
mkdir -p "$INSTALL_DIR"/{bin,lib,lib/adapters,lib/utils,logs}
curl -fsSL "$RAW_BASE/bin/feishu-receiver"        -o "$INSTALL_DIR/bin/feishu-receiver"
curl -fsSL "$RAW_BASE/lib/feishu-receiver.py"     -o "$INSTALL_DIR/lib/feishu-receiver.py"
curl -fsSL "$RAW_BASE/lib/config_manager.py"      -o "$INSTALL_DIR/lib/config_manager.py"
curl -fsSL "$RAW_BASE/lib/session_manager.py"     -o "$INSTALL_DIR/lib/session_manager.py"
curl -fsSL "$RAW_BASE/lib/message_processor.py"   -o "$INSTALL_DIR/lib/message_processor.py"
curl -fsSL "$RAW_BASE/lib/logger.py"              -o "$INSTALL_DIR/lib/logger.py"
curl -fsSL "$RAW_BASE/lib/adapters/__init__.py"   -o "$INSTALL_DIR/lib/adapters/__init__.py"
curl -fsSL "$RAW_BASE/lib/adapters/base.py"       -o "$INSTALL_DIR/lib/adapters/base.py"
curl -fsSL "$RAW_BASE/lib/adapters/claude.py"     -o "$INSTALL_DIR/lib/adapters/claude.py"
curl -fsSL "$RAW_BASE/lib/adapters/codex.py"      -o "$INSTALL_DIR/lib/adapters/codex.py"
curl -fsSL "$RAW_BASE/lib/adapters/opencode.py"   -o "$INSTALL_DIR/lib/adapters/opencode.py"
curl -fsSL "$RAW_BASE/lib/utils/__init__.py"      -o "$INSTALL_DIR/lib/utils/__init__.py"
curl -fsSL "$RAW_BASE/lib/utils/command.py"       -o "$INSTALL_DIR/lib/utils/command.py"

echo "==> 创建命令快捷方式..."
chmod +x "$INSTALL_DIR/lib/feishu-receiver.py" "$INSTALL_DIR/bin/feishu-receiver"
ln -sf "$INSTALL_DIR/bin/feishu-receiver" "$BIN_DIR/feishu-receiver"

echo "==> 创建 systemd 服务..."
cat > "$SYSTEMD_DIR/feishu-receiver.service" <<EOF
[Unit]
Description=Feishu Message Receiver
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=$INSTALL_DIR/bin/feishu-receiver foreground
Restart=on-failure
RestartSec=5
WorkingDirectory=$INSTALL_DIR
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
EOF
systemctl --user daemon-reload
systemctl --user enable feishu-receiver.service
systemctl --user restart feishu-receiver.service 2>/dev/null || true

echo ""
echo "========================================"
echo "安装完成！"
echo "========================================"
echo ""
echo "接下来请运行配置向导:"
echo ""
echo "  feishu-receiver setup"
echo ""
echo "或手动编辑配置文件: $INSTALL_DIR/config.json"
echo ""
echo "========================================"
