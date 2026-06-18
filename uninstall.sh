#!/usr/bin/env bash
set -euo pipefail

# 飞书消息接收服务卸载脚本
# 用法: ./uninstall.sh [--user]

INSTALL_MODE="user"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --user)
            INSTALL_MODE="user"
            shift
            ;;
        -h|--help)
            echo "用法: $0 [--user]"
            echo "  --user  卸载用户级安装"
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
        echo "系统级卸载需要 root 权限，请使用 sudo 运行，或添加 --user 进行用户级卸载。" >&2
        exit 1
    fi
    INSTALL_DIR="/opt/feishu-receiver"
    BIN_DIR="/usr/local/bin"
    SYSTEMD_DIR="/etc/systemd/system"
    SERVICE="feishu-receiver.service"

    if systemctl is-active --quiet "$SERVICE" 2>/dev/null; then
        echo "==> 停止 systemd 服务..."
        systemctl stop "$SERVICE"
    fi
    if systemctl is-enabled --quiet "$SERVICE" 2>/dev/null; then
        echo "==> 禁用 systemd 服务..."
        systemctl disable "$SERVICE"
    fi
    rm -f "$SYSTEMD_DIR/$SERVICE"
    systemctl daemon-reload
else
    INSTALL_DIR="${HOME}/.feishu-receiver"
    BIN_DIR="${HOME}/.local/bin"
    SYSTEMD_DIR="${HOME}/.config/systemd/user"
    SERVICE="feishu-receiver.service"

    if systemctl --user is-active --quiet "$SERVICE" 2>/dev/null; then
        echo "==> 停止 systemd 服务..."
        systemctl --user stop "$SERVICE"
    fi
    if systemctl --user is-enabled --quiet "$SERVICE" 2>/dev/null; then
        echo "==> 禁用 systemd 服务..."
        systemctl --user disable "$SERVICE"
    fi
    rm -f "$SYSTEMD_DIR/$SERVICE"
    systemctl --user daemon-reload
fi

echo "==> 停止独立进程..."
if [[ -f "$INSTALL_DIR/feishu-receiver.pid" ]]; then
    local_pid=$(cat "$INSTALL_DIR/feishu-receiver.pid" 2>/dev/null || true)
    if [[ -n "$local_pid" ]] && kill -0 "$local_pid" 2>/dev/null; then
        kill "$local_pid" 2>/dev/null || true
        sleep 1
        kill -9 "$local_pid" 2>/dev/null || true
    fi
    rm -f "$INSTALL_DIR/feishu-receiver.pid"
fi

echo "==> 删除命令快捷方式..."
rm -f "$BIN_DIR/feishu-receiver"

echo "==> 删除安装目录..."
if [[ -d "$INSTALL_DIR" ]]; then
    rm -rf "$INSTALL_DIR"
fi

echo ""
echo "========================================"
echo "卸载完成！"
echo "========================================"
