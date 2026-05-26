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

### One-Line Proxmox LXC Bootstrap

Run this from a Proxmox node shell as `root`:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/oculus-pllx/lxc-subnet-router/main/lxc-subnet-router-bootstrap.sh)
```

The bootstrapper creates the LXC, attaches `mgmt0` and any additional routed interfaces, installs the app, creates the router admin user, and seeds the initial interface config. It asks for:

| Prompt | Default | Notes |
|---|---|---|
| OS | Ubuntu 24.04 | Ubuntu 26.04 and Debian 13 are also offered |
| Container ID | next available | Resolved with Proxmox `pvesh` |
| Hostname | `lxc-subnet-router` | |
| Root password | none | Used for the LXC root account |
| Swap | Same as RAM | Re-prompts if a non-numeric value is entered |
| Router admin username/password | `admin` | Used for the web UI |
| Management bridge or SDN VNet | `vmbr0` | Shows detected Proxmox Linux bridges and SDN VNets, but allows manual entry |
| Management IP | manual | Use static CIDR for a fully automated install, or `dhcp` for temporary DHCP bootstrap networking |
| Additional routed interfaces | `2` | Each gets a friendly interface name, Proxmox bridge or SDN VNet, and optional static subnet gateway CIDR |

Proxmox attaches interfaces with `ip=manual`. The app owns the persistent in-container Netplan config. During bootstrap only, the script brings up temporary management networking so packages can install.

For each bridge/network prompt, choose one of the detected numbered options or type a bridge/VNet name manually. This supports standard Linux bridges such as `vmbr0` and Proxmox SDN VNets exposed through `pvesh get /cluster/sdn/vnets`.

Questionnaire entries re-prompt on validation errors instead of exiting. Mode answers such as `DHCP`, `dhcp`, `Manual`, and `static` are accepted case-insensitively.

If a container was created before a fix landed, update the app inside the container before using newer CLI commands:

```bash
pct exec <CT_ID> -- bash -lc 'cd /opt/lxc-subnet-router-src && git pull && ./install.sh'
```

DHCP interface config is persisted as Netplan `dhcp4: true`. IPv6 is disabled through generated Netplan (`dhcp6: false`, `accept-ra: false`, `link-local: []`) and sysctl (`disable_ipv6=1` for all/default/lo).

### Existing LXC Install

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
