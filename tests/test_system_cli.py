import subprocess
import sys

from lxc_subnet_router.system import parse_ip_addr_json, parse_routes


def test_parse_ip_addr_json_discovers_interfaces():
    payload = """
    [
      {
        "ifname": "mgmt0",
        "address": "aa:bb:cc:dd:ee:ff",
        "operstate": "UP",
        "stats64": {"rx": {"bytes": 10}, "tx": {"bytes": 20}},
        "addr_info": [{"family": "inet", "local": "10.0.0.2", "prefixlen": 24}]
      }
    ]
    """

    interfaces = parse_ip_addr_json(payload)

    assert interfaces[0]["name"] == "mgmt0"
    assert interfaces[0]["mac"] == "aa:bb:cc:dd:ee:ff"
    assert interfaces[0]["state"] == "UP"
    assert interfaces[0]["addresses"] == ["10.0.0.2/24"]
    assert interfaces[0]["rx_bytes"] == 10
    assert interfaces[0]["tx_bytes"] == 20


def test_parse_routes_marks_default_route():
    routes = parse_routes("default via 10.0.0.1 dev mgmt0\n192.168.10.0/24 dev vlan10 proto kernel\n")

    assert routes[0]["destination"] == "default"
    assert routes[0]["via"] == "10.0.0.1"
    assert routes[0]["interface"] == "mgmt0"
    assert routes[0]["default"] is True


def test_cli_preview_uses_config_file(tmp_path):
    config_path = tmp_path / "router.yaml"
    config_path.write_text(
        """
router:
  listen_host: 0.0.0.0
  listen_port: 8443
interfaces:
  mgmt0:
    role: management
    enabled: true
    address: 10.0.0.2/24
static_routes: []
groups: {}
users: {}
auth: {}
""",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "lxc_subnet_router.cli",
            "--config",
            str(config_path),
            "preview",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "mgmt0:" in result.stdout
    assert "10.0.0.2/24" in result.stdout


def test_cli_set_interface_updates_config(tmp_path):
    config_path = tmp_path / "router.yaml"

    subprocess.run(
        [sys.executable, "-m", "lxc_subnet_router.cli", "--config", str(config_path), "init"],
        check=True,
        capture_output=True,
        text=True,
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "lxc_subnet_router.cli",
            "--config",
            str(config_path),
            "set-interface",
            "mgmt0",
            "--role",
            "management",
            "--address",
            "10.0.0.2/24",
            "--gateway",
            "10.0.0.1",
            "--dns",
            "1.1.1.1,9.9.9.9",
            "--enabled",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "updated interface mgmt0" in result.stdout
    preview = subprocess.run(
        [sys.executable, "-m", "lxc_subnet_router.cli", "--config", str(config_path), "preview"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "10.0.0.2/24" in preview.stdout
    assert "via: 10.0.0.1" in preview.stdout


def test_cli_set_user_creates_admin_user_from_env(tmp_path, monkeypatch):
    config_path = tmp_path / "router.yaml"
    monkeypatch.setenv("ROUTER_PASSWORD", "secret-password")

    subprocess.run(
        [sys.executable, "-m", "lxc_subnet_router.cli", "--config", str(config_path), "init"],
        check=True,
        capture_output=True,
        text=True,
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "lxc_subnet_router.cli",
            "--config",
            str(config_path),
            "set-user",
            "routeradmin",
            "--group",
            "admin",
            "--password-env",
            "ROUTER_PASSWORD",
            "--enabled",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "updated user routeradmin" in result.stdout


def test_cli_verify_login_accepts_shell_sensitive_password(tmp_path, monkeypatch):
    config_path = tmp_path / "router.yaml"
    password = "DHCP! pass '$x\" ok"
    monkeypatch.setenv("ROUTER_PASSWORD", password)

    subprocess.run(
        [sys.executable, "-m", "lxc_subnet_router.cli", "--config", str(config_path), "init"],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "lxc_subnet_router.cli",
            "--config",
            str(config_path),
            "set-user",
            "routeradmin",
            "--group",
            "admin",
            "--password-env",
            "ROUTER_PASSWORD",
            "--enabled",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "lxc_subnet_router.cli",
            "--config",
            str(config_path),
            "verify-login",
            "routeradmin",
            "--password-env",
            "ROUTER_PASSWORD",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "login ok" in result.stdout
