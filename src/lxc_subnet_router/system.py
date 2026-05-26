from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from lxc_subnet_router.config import RouterConfig, validate_config
from lxc_subnet_router.netplan import generate_netplan


NETPLAN_PATH = Path("/etc/netplan/99-lxc-subnet-router.yaml")
SYSCTL_PATH = Path("/etc/sysctl.d/99-lxc-subnet-router.conf")


def run_command(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, check=False, capture_output=True, text=True)


def parse_ip_addr_json(output: str) -> list[dict[str, Any]]:
    raw = json.loads(output or "[]")
    interfaces = []
    for item in raw:
        stats = item.get("stats64") or {}
        rx = (stats.get("rx") or {}).get("bytes", 0)
        tx = (stats.get("tx") or {}).get("bytes", 0)
        addresses = []
        for address in item.get("addr_info", []):
            if address.get("family") in {"inet", "inet6"}:
                addresses.append(f"{address['local']}/{address['prefixlen']}")
        interfaces.append(
            {
                "name": item.get("ifname", ""),
                "mac": item.get("address", ""),
                "state": item.get("operstate", "UNKNOWN"),
                "addresses": addresses,
                "rx_bytes": rx,
                "tx_bytes": tx,
            }
        )
    return interfaces


def discover_interfaces() -> list[dict[str, Any]]:
    result = run_command(["ip", "-j", "addr", "show"])
    if result.returncode != 0:
        return []
    return parse_ip_addr_json(result.stdout)


def parse_routes(output: str) -> list[dict[str, Any]]:
    routes = []
    for line in output.splitlines():
        parts = line.split()
        if not parts:
            continue
        route = {
            "raw": line,
            "destination": parts[0],
            "via": "",
            "interface": "",
            "default": parts[0] == "default",
        }
        if "via" in parts:
            route["via"] = parts[parts.index("via") + 1]
        if "dev" in parts:
            route["interface"] = parts[parts.index("dev") + 1]
        routes.append(route)
    return routes


def current_routes() -> list[dict[str, Any]]:
    result = run_command(["ip", "route", "show"])
    if result.returncode != 0:
        return []
    return parse_routes(result.stdout)


def forwarding_status() -> dict[str, str]:
    ipv4 = run_command(["sysctl", "-n", "net.ipv4.ip_forward"])
    ipv6 = run_command(["sysctl", "-n", "net.ipv6.conf.all.forwarding"])
    return {
        "ipv4": ipv4.stdout.strip() if ipv4.returncode == 0 else "unknown",
        "ipv6": ipv6.stdout.strip() if ipv6.returncode == 0 else "unknown",
    }


def write_pending_files(config: RouterConfig, netplan_path: Path = NETPLAN_PATH, sysctl_path: Path = SYSCTL_PATH) -> None:
    netplan_path.parent.mkdir(parents=True, exist_ok=True)
    sysctl_path.parent.mkdir(parents=True, exist_ok=True)
    netplan_path.write_text(generate_netplan(config), encoding="utf-8")
    sysctl_path.write_text(
        "\n".join(
            [
                "net.ipv4.ip_forward=1" if config.router.get("ipv4_forwarding", True) else "net.ipv4.ip_forward=0",
                "net.ipv6.conf.all.forwarding=1"
                if config.router.get("ipv6_forwarding", False)
                else "net.ipv6.conf.all.forwarding=0",
                "",
            ]
        ),
        encoding="utf-8",
    )


def backup_file(path: Path) -> Path | None:
    if not path.exists():
        return None
    backup = path.with_suffix(path.suffix + ".bak")
    shutil.copy2(path, backup)
    return backup


def validate_for_host(config: RouterConfig) -> list[str]:
    return validate_config(config.data, [item["name"] for item in discover_interfaces()])


def apply_config(config: RouterConfig, dry_run: bool = False) -> list[str]:
    errors = validate_for_host(config)
    if errors:
        return errors
    if dry_run:
        return []
    backup_file(NETPLAN_PATH)
    backup_file(SYSCTL_PATH)
    write_pending_files(config)
    for command in (["netplan", "generate"], ["sysctl", "--system"], ["netplan", "apply"]):
        result = run_command(command)
        if result.returncode != 0:
            return [result.stderr.strip() or result.stdout.strip() or f"{' '.join(command)} failed"]
    return []
