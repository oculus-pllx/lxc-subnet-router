# LXC Subnet Router

Lightweight Proxmox LXC subnet router manager. It enables Linux IP forwarding, generates Netplan config, and provides a small FastAPI web UI plus a recovery CLI.

This is not a firewall and not a NAT gateway. It does not install or manage UFW, nftables, iptables filtering, masquerade, or port forwarding.

## Targets

- Ubuntu 24.04 LXC by default
- Ubuntu 26.04 LXC supported
- Debian latest supported
- Privileged LXC recommended

## Proxmox Network Model

Let Proxmox attach interfaces and bridges, but leave IP assignment to the app:

```text
net0: name=mgmt0,bridge=vmbr0,ip=manual
net1: name=vlan10,bridge=vmbr10,ip=manual
net2: name=vlan20,bridge=vmbr20,ip=manual
```

Clients on each routed subnet should use the LXC interface IP as their gateway.

## Install

Inside the LXC:

```bash
git clone https://github.com/oculus-pllx/lxc-subnet-router.git
cd lxc-subnet-router
sudo ./install.sh
```

The web UI listens on `0.0.0.0:8443` by default and uses dark mode by default. Initial auth uses a local admin user created by the installer.

After login, open **Wizard** to configure the management interface and routed subnet interfaces. The wizard defaults management to `mgmt0` when it exists. Management stays separate from routed subnet interfaces; routed rows are configured only when you provide each subnet gateway CIDR.

## CLI

```bash
lxc-subnet-router status
lxc-subnet-router interfaces
lxc-subnet-router routes
lxc-subnet-router preview
lxc-subnet-router apply --dry-run
lxc-subnet-router apply
lxc-subnet-router rollback
lxc-subnet-router health
lxc-subnet-router set-interface mgmt0 --role management --address 10.11.200.68/24 --gateway 10.11.200.1 --dns 1.1.1.1,9.9.9.9 --enabled
lxc-subnet-router set-interface vlan10 --role routed --address 192.168.10.1/24 --enabled
lxc-subnet-router add-route 192.168.50.0/24 --via 10.11.200.1 --interface mgmt0 --metric 100
```

When installed under `/opt`, use:

```bash
/opt/lxc-subnet-router/venv/bin/lxc-subnet-router --config /opt/lxc-subnet-router/config/router.yaml status
```

Example first configuration:

```bash
ROUTER="/opt/lxc-subnet-router/venv/bin/lxc-subnet-router --config /opt/lxc-subnet-router/config/router.yaml"
$ROUTER set-interface mgmt0 --role management --address 10.11.200.68/24 --gateway 10.11.200.1 --dns 1.1.1.1,9.9.9.9 --enabled
$ROUTER set-interface vlan10 --role routed --address 192.168.10.1/24 --enabled
$ROUTER set-interface vlan20 --role routed --address 192.168.20.1/24 --enabled
$ROUTER preview
$ROUTER apply --dry-run
$ROUTER apply
```

## Config

Primary config:

```text
/opt/lxc-subnet-router/config/router.yaml
```

Generated Netplan:

```text
/etc/netplan/99-lxc-subnet-router.yaml
```

Forwarding sysctl:

```text
/etc/sysctl.d/99-lxc-subnet-router.conf
```

## Development

```bash
uv venv .venv
.venv/bin/python -m ensurepip
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/python -m pytest
```

Run the web UI locally with an auth-disabled test config:

```bash
.venv/bin/uvicorn lxc_subnet_router.web:app --host 0.0.0.0 --port 8443
```
