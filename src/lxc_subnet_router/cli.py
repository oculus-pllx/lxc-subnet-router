from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from lxc_subnet_router.auth import hash_password
from lxc_subnet_router.config import RouterConfig, default_config, load_or_default
from lxc_subnet_router.netplan import generate_netplan
from lxc_subnet_router.system import apply_config, current_routes, discover_interfaces, forwarding_status


def _load(path: Path) -> RouterConfig:
    return load_or_default(path, [item["name"] for item in discover_interfaces()])


def cmd_init(args: argparse.Namespace) -> int:
    interfaces = [item["name"] for item in discover_interfaces()] or ["mgmt0"]
    data = default_config(interfaces)
    if args.admin_password:
        data["users"]["admin"] = {
            "enabled": True,
            "group": "admin",
            "password_hash": hash_password(args.admin_password),
        }
    RouterConfig.from_dict(data).save(args.config)
    print(f"wrote {args.config}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    config = _load(args.config)
    status = forwarding_status()
    print(f"config: {args.config}")
    print(f"listen: {config.router.get('listen_host', '0.0.0.0')}:{config.router.get('listen_port', 8443)}")
    print(f"ipv4_forwarding: {status['ipv4']}")
    print(f"ipv6_forwarding: {status['ipv6']}")
    print(f"interfaces: {len(discover_interfaces())}")
    print(f"routes: {len(current_routes())}")
    return 0


def cmd_interfaces(args: argparse.Namespace) -> int:
    for item in discover_interfaces():
        print(f"{item['name']}\t{item['state']}\t{','.join(item['addresses'])}\t{item['mac']}")
    return 0


def cmd_routes(args: argparse.Namespace) -> int:
    for route in current_routes():
        print(route["raw"])
    return 0


def cmd_preview(args: argparse.Namespace) -> int:
    print(generate_netplan(_load(args.config)))
    return 0


def cmd_set_interface(args: argparse.Namespace) -> int:
    config = _load(args.config)
    item = config.data.setdefault("interfaces", {}).setdefault(args.name, {})
    if args.role:
        item["role"] = args.role
    if args.address is not None:
        item["address"] = args.address
    if args.gateway is not None:
        item["gateway"] = args.gateway
    if args.dns is not None:
        item["dns"] = [entry.strip() for entry in args.dns.split(",") if entry.strip()]
    if args.enabled:
        item["enabled"] = True
    if args.disabled:
        item["enabled"] = False
    config.save(args.config)
    print(f"updated interface {args.name}")
    return 0


def cmd_add_route(args: argparse.Namespace) -> int:
    config = _load(args.config)
    route = {
        "destination": args.destination,
        "via": args.via,
        "interface": args.interface,
        "metric": args.metric,
        "enabled": True,
    }
    config.data.setdefault("static_routes", []).append(route)
    config.save(args.config)
    print(f"added route {args.destination} via {args.via}")
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    errors = apply_config(_load(args.config), dry_run=args.dry_run)
    if errors:
        for error in errors:
            print(f"error: {error}")
        return 1
    print("dry-run ok" if args.dry_run else "applied")
    return 0


def cmd_health(args: argparse.Namespace) -> int:
    config = _load(args.config)
    print(yaml.safe_dump({"forwarding": forwarding_status(), "routes": current_routes(), "config": config.data}, sort_keys=False))
    return 0


def cmd_rollback(args: argparse.Namespace) -> int:
    print("restore /etc/netplan/99-lxc-subnet-router.yaml.bak and run netplan apply if console rollback is needed")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lxc-subnet-router")
    parser.add_argument("--config", type=Path, default=Path("/opt/lxc-subnet-router/config/router.yaml"))
    subparsers = parser.add_subparsers(dest="command", required=True)
    init = subparsers.add_parser("init")
    init.add_argument("--admin-password")
    init.set_defaults(func=cmd_init)
    for name, func in {
        "status": cmd_status,
        "interfaces": cmd_interfaces,
        "routes": cmd_routes,
        "preview": cmd_preview,
        "health": cmd_health,
        "rollback": cmd_rollback,
    }.items():
        subparsers.add_parser(name).set_defaults(func=func)
    apply_parser = subparsers.add_parser("apply")
    apply_parser.add_argument("--dry-run", action="store_true")
    apply_parser.set_defaults(func=cmd_apply)
    set_interface = subparsers.add_parser("set-interface")
    set_interface.add_argument("name")
    set_interface.add_argument("--role", choices=["management", "routed", "unused"])
    set_interface.add_argument("--address")
    set_interface.add_argument("--gateway")
    set_interface.add_argument("--dns")
    set_interface.add_argument("--enabled", action="store_true")
    set_interface.add_argument("--disabled", action="store_true")
    set_interface.set_defaults(func=cmd_set_interface)
    add_route = subparsers.add_parser("add-route")
    add_route.add_argument("destination")
    add_route.add_argument("--via", required=True)
    add_route.add_argument("--interface", required=True)
    add_route.add_argument("--metric", type=int, default=100)
    add_route.set_defaults(func=cmd_add_route)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
