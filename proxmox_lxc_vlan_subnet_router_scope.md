# Proxmox LXC VLAN/Subnet Router Scope

## Purpose

Build a lightweight Ubuntu 26.04 LXC-based subnet router for Proxmox.

This system is **not a firewall**, **not a NAT gateway**, and **not a security appliance**. It should behave like a Layer 3 switch/router: traffic enters on one subnet/VLAN interface and is forwarded out the correct subnet/VLAN interface based on the Linux routing table.

The goal is simple, predictable routing between VLANs, bridges, and lab subnets.

---

## Core Design Principle

> Forward packets between connected subnets without filtering, NAT, inspection, or policy enforcement.

The router should:

- Route between directly connected subnets
- Forward all allowed IP traffic by default
- Avoid NAT by default
- Avoid firewall rules by default
- Avoid packet filtering by default
- Use standard Linux routing behavior
- Provide a management GUI because the LXC is headless

This should feel closer to a **Layer 3 switch SVI setup** than a firewall/router appliance like pfSense or OPNsense.

---

## Target Platform

| Component | Requirement |
|---|---|
| Host | Proxmox VE |
| Guest | Ubuntu 26.04 LXC |
| LXC Type | Prefer privileged LXC |
| Networking | Multiple Proxmox bridges or VLAN-backed interfaces |
| Routing | Linux kernel routing |
| Config | Netplan + sysctl |
| GUI | Lightweight local web interface |
| Firewall | None by default |
| NAT | None by default |

---

## Example Network Model

```text
                 Proxmox Host
                     |
        -----------------------------
        |             |             |
      vmbr0         vmbr10        vmbr20
   Management       VLAN 10       VLAN 20
        |             |             |
      mgmt0         vlan10        vlan20
        \             |             /
         \            |            /
          Ubuntu LXC Subnet Router
```

Example addressing:

| Interface | Purpose | Address |
|---|---|---|
| `mgmt0` | Management | `10.11.200.68/24` |
| `vlan10` | Routed subnet | `192.168.10.1/24` |
| `vlan20` | Routed subnet | `192.168.20.1/24` |
| `vlan30` | Routed subnet | `192.168.30.1/24` |

Clients on each subnet use the LXC router address as their gateway.

Example:

| Client Subnet | Client Gateway |
|---|---|
| `192.168.10.0/24` | `192.168.10.1` |
| `192.168.20.0/24` | `192.168.20.1` |
| `192.168.30.0/24` | `192.168.30.1` |

---

## What This System Is

This system is:

- A subnet router
- A VLAN router
- A routed gateway between Proxmox bridges
- A Linux-based Layer 3 forwarding node
- A GUI-managed routing appliance
- A headless LXC routing controller

---

## What This System Is Not

This system is **not**:

- A firewall
- A NAT router
- A WAN edge device
- A packet inspection appliance
- A VPN gateway by default
- A pfSense replacement
- An OPNsense replacement
- A Zero Trust policy router
- A security boundary by default

---

## Functional Requirements

### 1. IP Forwarding

The system must enable IPv4 forwarding.

Required sysctl setting:

```bash
net.ipv4.ip_forward=1
```

Stored in:

```text
/etc/sysctl.d/99-lxc-subnet-router.conf
```

IPv6 forwarding should be disabled by default unless explicitly enabled later.

```bash
net.ipv6.conf.all.forwarding=0
```

---

### 2. Interface Discovery

The system must discover available interfaces inside the LXC.

It should show:

- Interface name
- MAC address
- Current IP address
- Link state
- Assigned role
- RX/TX statistics
- Default route status

Example roles:

| Role | Description |
|---|---|
| `management` | GUI and admin access |
| `routed` | Participates in subnet routing |
| `unused` | Present but ignored |

There should be no `WAN`, `LAN`, or firewall-style role naming in the MVP.

Preferred terminology:

- Management interface
- Routed interface
- Subnet interface
- VLAN interface

---

### 3. Netplan Management

The system should generate Netplan configuration from a YAML config file.

Target file:

```text
/etc/netplan/99-lxc-subnet-router.yaml
```

Example generated Netplan:

```yaml
network:
  version: 2
  renderer: networkd

  ethernets:
    mgmt0:
      addresses:
        - 10.11.200.68/24
      routes:
        - to: default
          via: 10.11.200.1
      nameservers:
        addresses:
          - 1.1.1.1
          - 9.9.9.9

    vlan10:
      addresses:
        - 192.168.10.1/24

    vlan20:
      addresses:
        - 192.168.20.1/24

    vlan30:
      addresses:
        - 192.168.30.1/24
```

---

### 4. Directly Connected Routing

The primary routing behavior should come from directly connected interfaces.

If the LXC has:

```text
vlan10 = 192.168.10.1/24
vlan20 = 192.168.20.1/24
```

Linux automatically creates connected routes:

```text
192.168.10.0/24 dev vlan10
192.168.20.0/24 dev vlan20
```

Traffic from `192.168.10.0/24` to `192.168.20.0/24` should forward normally if:

1. Clients use the LXC as their gateway
2. IP forwarding is enabled
3. Return routes exist
4. Proxmox bridges/VLANs are correctly attached

---

### 5. Static Route Management

The GUI should allow optional static routes for non-directly-connected networks.

Example use case:

```text
Route 192.168.50.0/24 through next hop 10.11.200.1
```

Static route fields:

| Field | Example |
|---|---|
| Destination | `192.168.50.0/24` |
| Next Hop | `10.11.200.1` |
| Interface | `mgmt0` |
| Metric | `100` |
| Enabled | `true` |

Example Netplan route:

```yaml
routes:
  - to: 192.168.50.0/24
    via: 10.11.200.1
    metric: 100
```

---

## Explicit Firewall/NAT Policy

### Firewall

The MVP should not create firewall rules.

Default behavior:

```text
No packet filtering.
No subnet blocking.
No default deny.
No ACL enforcement.
```

Do not install or configure UFW.

Do not create nftables filtering rules.

Do not create iptables filtering rules.

---

### NAT

The MVP should not perform NAT.

Default behavior:

```text
No masquerade.
No source NAT.
No destination NAT.
No port forwarding.
```

Traffic should remain routed, not translated.

Each subnet should be reachable using its real source and destination IP addresses.

---

## Management GUI Requirements

Because the LXC is headless, the system needs a simple web GUI.

### Recommended Stack

| Layer | Technology |
|---|---|
| Backend | Python FastAPI |
| Templates | Jinja2 |
| UI | HTMX + Bootstrap or Tailwind |
| Config | YAML |
| Service | systemd |
| Auth | Local admin password |
| HTTPS | Self-signed cert or optional Caddy |

Avoid a heavy frontend framework for MVP.

---

## GUI Pages

### 1. Dashboard

Show:

- Router status
- IPv4 forwarding status
- Interface summary
- Routing table summary
- Management URL
- System uptime

Status indicators:

| Check | Expected |
|---|---|
| IPv4 forwarding | Enabled |
| Management interface | Up |
| Routed interfaces | Up |
| Default route | Present if configured |
| Firewall | Not active / unmanaged |
| NAT | Not active / unmanaged |

---

### 2. Interfaces

Show all interfaces.

Fields:

- Name
- Role
- IP address/CIDR
- Gateway if any
- DNS if any
- Link state
- MAC address
- RX/TX stats

Actions:

- Assign role
- Set static IP
- Set gateway only on management/uplink interface
- Enable or disable interface from generated config

---

### 3. Static Routes

Show static routes.

Actions:

- Add route
- Disable route
- Delete route
- Validate route

---

### 4. Routing Table

Read-only page showing:

```bash
ip route show
```

Also show:

```bash
ip addr show
```

---

### 5. Apply / Rollback

The GUI must support safe configuration application.

Actions:

- Preview generated Netplan
- Apply config
- Roll back to previous config
- Reboot container warning if needed

---

## Configuration File

Primary app config:

```text
/opt/lxc-subnet-router/config/router.yaml
```

Example:

```yaml
router:
  ipv4_forwarding: true
  ipv6_forwarding: false
  firewall_managed: false
  nat_managed: false

interfaces:
  mgmt0:
    role: management
    enabled: true
    address: 10.11.200.68/24
    gateway: 10.11.200.1
    dns:
      - 1.1.1.1
      - 9.9.9.9

  vlan10:
    role: routed
    enabled: true
    address: 192.168.10.1/24

  vlan20:
    role: routed
    enabled: true
    address: 192.168.20.1/24

  vlan30:
    role: routed
    enabled: true
    address: 192.168.30.1/24

static_routes:
  - destination: 192.168.50.0/24
    via: 10.11.200.1
    interface: mgmt0
    metric: 100
    enabled: true
```

---

## Safe Apply Process

All changes should be staged and validated before applying.

Process:

```text
1. Load current config
2. Load proposed config
3. Validate YAML syntax
4. Validate IP/CIDR values
5. Validate gateway addresses
6. Validate interface names exist
7. Backup current app config
8. Backup current Netplan config
9. Generate new Netplan config
10. Write pending Netplan file
11. Run netplan generate
12. Run netplan try where available
13. Apply sysctl forwarding setting
14. Verify route table
15. Commit app config
16. Roll back on failure
```

Preferred apply command:

```bash
netplan try --timeout 30
```

Fallback:

```bash
netplan apply
```

---

## CLI Recovery Tool

Install a command:

```bash
lxc-subnet-router
```

Commands:

```bash
lxc-subnet-router status
lxc-subnet-router interfaces
lxc-subnet-router routes
lxc-subnet-router preview
lxc-subnet-router apply
lxc-subnet-router rollback
lxc-subnet-router health
```

This is required so the router can be recovered over console or SSH if the GUI becomes unreachable.

---

## Health Checks

Health script:

```text
/opt/lxc-subnet-router/scripts/health-check.sh
```

Checks:

```bash
sysctl net.ipv4.ip_forward
ip addr show
ip route show
networkctl status
ping -c 2 <default_gateway>
```

Optional route test:

```bash
ping -c 2 <known_host_on_each_subnet>
```

Do not require internet access for health to pass.

This router may be used in isolated lab networks.

---

## Installer Requirements

Installer path:

```text
install.sh
```

The installer should:

```text
1. Confirm Ubuntu 26.04
2. Confirm root execution
3. Install required packages
4. Create /opt/lxc-subnet-router
5. Create config directory
6. Detect interfaces
7. Generate starter router.yaml
8. Enable IPv4 forwarding
9. Create Python virtual environment
10. Install FastAPI app dependencies
11. Install systemd service
12. Start GUI service
13. Print management URL
```

Required packages:

```bash
python3
python3-venv
python3-pip
netplan.io
iproute2
systemd
curl
jq
openssl
```

Do not install by default:

```bash
ufw
firewalld
iptables-persistent
frr
```

---

## Systemd Service

Service name:

```text
lxc-subnet-router.service
```

Example:

```ini
[Unit]
Description=LXC Subnet Router Manager
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/lxc-subnet-router/app
ExecStart=/opt/lxc-subnet-router/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8443
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

The service may run as root in MVP because it needs to write Netplan and apply network changes.

A later version can split GUI and privileged helper service.

---

## Security Model

This tool does not enforce network security.

Security focus is only for the management interface.

Management GUI should include:

- Login page
- Local admin password
- Password hash storage
- Session cookie
- HTTPS option

Network forwarding should remain unrestricted.

---

## Proxmox LXC Notes

Recommended container type:

```text
Privileged LXC
```

Recommended features:

```text
nesting=1
keyctl=1
```

Example Proxmox network layout:

```text
net0: name=mgmt0,bridge=vmbr0,ip=10.11.200.68/24,gw=10.11.200.1
net1: name=vlan10,bridge=vmbr10,ip=manual
net2: name=vlan20,bridge=vmbr20,ip=manual
net3: name=vlan30,bridge=vmbr30,ip=manual
```

Inside the LXC, the application owns IP addressing for the routed interfaces.

---

## Routing Behavior Example

### Desired Behavior

Host A:

```text
IP: 192.168.10.50
Gateway: 192.168.10.1
```

Host B:

```text
IP: 192.168.20.50
Gateway: 192.168.20.1
```

Router:

```text
vlan10: 192.168.10.1/24
vlan20: 192.168.20.1/24
ip_forward=1
```

Expected result:

```text
192.168.10.50 can reach 192.168.20.50
192.168.20.50 can reach 192.168.10.50
```

No NAT.

No firewall.

No translation.

Just routing.

---

## Non-Goals for MVP

Do not build these into MVP:

- Firewall policy engine
- NAT rules
- Port forwarding
- VPN server
- Dynamic routing
- DHCP server
- DNS server
- IDS/IPS
- Captive portal
- Multi-user RBAC
- Cloud sync

Possible future features:

- FRRouting support
- VLAN subinterface creation
- DHCP relay
- Route monitoring
- Prometheus exporter
- Config backup/export

---

## Acceptance Criteria

The project is complete when:

1. Ubuntu 26.04 LXC boots normally
2. GUI is reachable from management interface
3. Interfaces are detected correctly
4. Static IPs can be assigned to routed interfaces
5. IPv4 forwarding is enabled persistently
6. Directly connected subnets route through the LXC
7. No NAT is configured
8. No firewall rules are configured by the app
9. Netplan config survives reboot
10. CLI recovery tool works
11. Bad network config can be rolled back
12. README explains Proxmox LXC setup clearly

---

## Codex Build Prompt

Use this prompt to start the build:

```text
Build a production-ready Ubuntu 26.04 Proxmox LXC subnet router manager.

This is not a firewall and not a NAT gateway. It should behave like a Layer 3 switch/router that forwards traffic between connected Proxmox bridges, VLANs, and subnets. The default behavior must be unrestricted routing between directly connected subnets using Linux kernel IP forwarding.

Use Python FastAPI, Jinja2 templates, HTMX, and Bootstrap or Tailwind for a lightweight web GUI. Store configuration in YAML under /opt/lxc-subnet-router/config/router.yaml. Generate Netplan configuration from this YAML and apply it safely with validation, backup, and rollback.

Requirements:
- Ubuntu 26.04 LXC target
- Proxmox LXC compatibility
- Interface discovery
- Management and routed interface roles
- IPv4 forwarding enabled persistently
- IPv6 forwarding disabled by default
- Static route management
- Generated Netplan config
- Safe apply and rollback
- CLI recovery command named lxc-subnet-router
- Dashboard showing forwarding, interfaces, and route table
- No firewall rules by default
- No NAT by default
- Do not install or configure UFW
- Do not configure nftables or iptables filtering
- Do not require internet access for health checks

Default routing model:
Traffic should route freely between all directly connected subnets as long as hosts use the LXC interface IP as their gateway and return routes exist.

Prioritize reliability, simple recovery, and clear generated configuration over visual complexity.
```

---

## Recommended MVP Name

Suggested name:

```text
L3-LXC Router
```

Alternative names:

- LXC Subnet Router
- Proxmox L3 Router
- VLAN RouteBox
- LXC RouteBridge
- Subnet Fabric Router

Best practical name for the repo:

```text
lxc-subnet-router
```

