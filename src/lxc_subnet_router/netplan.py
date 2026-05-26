from __future__ import annotations

import yaml

from lxc_subnet_router.config import RouterConfig


def generate_netplan(config: RouterConfig) -> str:
    ethernets: dict = {}
    for name, item in config.interfaces.items():
        if not item.get("enabled", True):
            continue
        ethernet: dict = {}
        address = item.get("address")
        ethernet["dhcp6"] = False
        ethernet["accept-ra"] = False
        ethernet["link-local"] = []
        if item.get("dhcp4"):
            ethernet["dhcp4"] = True
        if address:
            ethernet["addresses"] = [address]
        routes = []
        gateway = item.get("gateway")
        if gateway:
            routes.append({"to": "default", "via": gateway})
        for route in config.static_routes:
            if not route.get("enabled", True):
                continue
            if route.get("interface") and route.get("interface") != name:
                continue
            entry = {"to": route["destination"], "via": route["via"]}
            if route.get("metric") is not None:
                entry["metric"] = int(route["metric"])
            routes.append(entry)
        if routes:
            ethernet["routes"] = routes
        dns = item.get("dns") or []
        if dns:
            ethernet["nameservers"] = {"addresses": dns}
        ethernets[name] = ethernet

    payload = {"network": {"version": 2, "renderer": "networkd", "ethernets": ethernets}}
    return yaml.safe_dump(payload, sort_keys=False)
