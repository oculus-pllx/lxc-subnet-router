from __future__ import annotations

from dataclasses import dataclass
from ipaddress import ip_address, ip_interface, ip_network
from pathlib import Path
from typing import Any

import yaml


DEFAULT_CONFIG_PATH = Path("/opt/lxc-subnet-router/config/router.yaml")


def default_config(interface_names: list[str] | None = None) -> dict[str, Any]:
    interface_names = interface_names or ["mgmt0"]
    interfaces: dict[str, Any] = {}
    for name in interface_names:
        if name == "lo":
            continue
        role = "management" if name == "mgmt0" else "unused"
        interfaces[name] = {"role": role, "enabled": name == "mgmt0", "address": ""}

    interfaces.setdefault("mgmt0", {"role": "management", "enabled": True, "address": ""})

    return {
        "router": {
            "ipv4_forwarding": True,
            "ipv6_forwarding": False,
            "firewall_managed": False,
            "nat_managed": False,
            "listen_host": "0.0.0.0",
            "listen_port": 8443,
        },
        "auth": {
            "enabled": True,
            "session_timeout_minutes": 60,
            "password_hash_algorithm": "argon2id",
            "session_secret": "",
        },
        "groups": {
            "admin": {
                "permissions": [
                    "view_status",
                    "view_config",
                    "view_interfaces",
                    "view_routes",
                    "manage_interfaces",
                    "manage_routes",
                    "apply_config",
                    "rollback_config",
                    "manage_users",
                ]
            },
            "operator": {
                "permissions": [
                    "view_status",
                    "view_config",
                    "view_interfaces",
                    "view_routes",
                    "manage_interfaces",
                    "manage_routes",
                    "apply_config",
                    "rollback_config",
                ]
            },
            "viewer": {
                "permissions": [
                    "view_status",
                    "view_config",
                    "view_interfaces",
                    "view_routes",
                ]
            },
        },
        "users": {},
        "interfaces": interfaces,
        "static_routes": [],
    }


@dataclass(frozen=True)
class RouterConfig:
    data: dict[str, Any]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RouterConfig":
        return cls(data)

    @classmethod
    def load(cls, path: Path = DEFAULT_CONFIG_PATH) -> "RouterConfig":
        with path.open("r", encoding="utf-8") as handle:
            return cls.from_dict(yaml.safe_load(handle) or {})

    def save(self, path: Path = DEFAULT_CONFIG_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(self.data, handle, sort_keys=False)

    @property
    def router(self) -> dict[str, Any]:
        return self.data.get("router", {})

    @property
    def interfaces(self) -> dict[str, Any]:
        return self.data.get("interfaces", {})

    @property
    def static_routes(self) -> list[dict[str, Any]]:
        return self.data.get("static_routes", [])


def load_or_default(path: Path = DEFAULT_CONFIG_PATH, interfaces: list[str] | None = None) -> RouterConfig:
    if path.exists():
        return RouterConfig.load(path)
    return RouterConfig.from_dict(default_config(interfaces))


def validate_config(config: dict[str, Any], existing_interfaces: list[str] | None = None) -> list[str]:
    errors: list[str] = []
    interfaces = config.get("interfaces", {})
    management = [name for name, item in interfaces.items() if item.get("role") == "management"]
    if len(management) != 1:
        errors.append("one management interface is required")

    existing = set(existing_interfaces or interfaces.keys())
    for name, item in interfaces.items():
        if name not in existing:
            errors.append(f"interface {name} does not exist")
        address = item.get("address")
        if item.get("enabled") and address:
            try:
                ip_interface(address)
            except ValueError:
                errors.append(f"interface {name} has invalid address {address}")
        gateway = item.get("gateway")
        if gateway:
            try:
                ip_address(gateway)
            except ValueError:
                errors.append(f"interface {name} has invalid gateway {gateway}")

    for route in config.get("static_routes", []):
        if not route.get("enabled", True):
            continue
        try:
            ip_network(route.get("destination", ""), strict=False)
        except ValueError:
            errors.append(f"route has invalid destination {route.get('destination')}")
        try:
            ip_address(route.get("via", ""))
        except ValueError:
            errors.append(f"route has invalid next hop {route.get('via')}")
        if route.get("interface") and route["interface"] not in interfaces:
            errors.append(f"route interface {route['interface']} is not configured")

    return errors
