#!/usr/bin/env bash
set -euo pipefail

APP_DIR=/opt/lxc-subnet-router
CONFIG_DIR="$APP_DIR/config"
CONFIG_FILE="$CONFIG_DIR/router.yaml"
SERVICE_FILE=/etc/systemd/system/lxc-subnet-router.service

if [[ "$(id -u)" -ne 0 ]]; then
  echo "install.sh must run as root" >&2
  exit 1
fi

if [[ ! -r /etc/os-release ]]; then
  echo "cannot read /etc/os-release" >&2
  exit 1
fi

. /etc/os-release
case "${ID}:${VERSION_ID:-}" in
  ubuntu:24.04|ubuntu:26.04|debian:*)
    ;;
  *)
    echo "warning: untested OS ${PRETTY_NAME:-unknown}; continuing" >&2
    ;;
esac

echo "Installing packages..."
apt-get update
apt-get install -y python3 python3-venv python3-pip netplan.io iproute2 systemd curl jq openssl

echo "Installing application..."
mkdir -p "$APP_DIR" "$CONFIG_DIR"
cp -a pyproject.toml requirements.txt src "$APP_DIR/"
python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/python" -m pip install --upgrade pip
"$APP_DIR/venv/bin/python" -m pip install "$APP_DIR"

if [[ ! -f "$CONFIG_FILE" ]]; then
  ADMIN_USER="${LXC_SUBNET_ROUTER_ADMIN_USER:-admin}"
  ADMIN_PASSWORD="${LXC_SUBNET_ROUTER_ADMIN_PASSWORD:-}"
  if [[ -z "$ADMIN_PASSWORD" ]]; then
    read -r -s -p "Initial admin password: " ADMIN_PASSWORD
    echo
  fi
  "$APP_DIR/venv/bin/lxc-subnet-router" --config "$CONFIG_FILE" init --admin-password "$ADMIN_PASSWORD"
  if [[ "$ADMIN_USER" != "admin" ]]; then
    LXC_SUBNET_ROUTER_PASSWORD="$ADMIN_PASSWORD" "$APP_DIR/venv/bin/lxc-subnet-router" --config "$CONFIG_FILE" set-user "$ADMIN_USER" --group admin --password-env LXC_SUBNET_ROUTER_PASSWORD --enabled
    "$APP_DIR/venv/bin/lxc-subnet-router" --config "$CONFIG_FILE" set-user admin --disabled
  fi
fi

cat >/etc/sysctl.d/99-lxc-subnet-router.conf <<'SYSCTL'
net.ipv4.ip_forward=1
net.ipv6.conf.all.forwarding=0
net.ipv6.conf.default.forwarding=0
net.ipv6.conf.all.disable_ipv6=1
net.ipv6.conf.default.disable_ipv6=1
net.ipv6.conf.lo.disable_ipv6=1
SYSCTL
sysctl --system >/dev/null

cp lxc-subnet-router.service "$SERVICE_FILE"
systemctl daemon-reload
systemctl enable --now lxc-subnet-router.service

MGMT_IP="$(ip -4 -j addr show | jq -r '.[] | select(.ifname=="mgmt0") | .addr_info[]? | select(.family=="inet") | .local' | head -n1)"
if [[ -z "$MGMT_IP" ]]; then
  MGMT_IP="$(hostname -I | awk '{print $1}')"
fi

echo "LXC Subnet Router installed."
echo "Management URL: http://${MGMT_IP:-127.0.0.1}:8443/"
echo "CLI: $APP_DIR/venv/bin/lxc-subnet-router --config $CONFIG_FILE status"
