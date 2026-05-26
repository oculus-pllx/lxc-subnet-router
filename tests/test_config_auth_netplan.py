from lxc_subnet_router.auth import can, hash_password, verify_password
from lxc_subnet_router.config import RouterConfig, default_config, validate_config
from lxc_subnet_router.netplan import generate_netplan


def test_default_config_has_groups_and_app_owned_management():
    config = default_config(["mgmt0", "vlan10"])

    assert config["router"]["listen_host"] == "0.0.0.0"
    assert config["interfaces"]["mgmt0"]["role"] == "management"
    assert config["interfaces"]["mgmt0"]["enabled"] is True
    assert config["interfaces"]["vlan10"]["role"] == "unused"
    assert config["interfaces"]["vlan10"]["enabled"] is False
    assert set(config["groups"]) == {"admin", "operator", "viewer"}


def test_validate_config_rejects_missing_management_interface():
    config = default_config(["vlan10"])
    del config["interfaces"]["mgmt0"]

    errors = validate_config(config, existing_interfaces=["vlan10"])

    assert "one management interface is required" in errors


def test_role_permissions_match_mvp_groups():
    config = default_config(["mgmt0"])

    assert can(config, "admin", "manage_users")
    assert can(config, "operator", "apply_config")
    assert not can(config, "operator", "manage_users")
    assert can(config, "viewer", "view_routes")
    assert not can(config, "viewer", "apply_config")


def test_password_hash_verifies_and_rejects_wrong_password():
    password_hash = hash_password("correct horse battery staple")

    assert verify_password(password_hash, "correct horse battery staple")
    assert not verify_password(password_hash, "wrong")


def test_generate_netplan_includes_management_and_static_routes():
    config = RouterConfig.from_dict(
        {
            **default_config(["mgmt0", "vlan10"]),
            "interfaces": {
                "mgmt0": {
                    "role": "management",
                    "enabled": True,
                    "address": "10.11.200.68/24",
                    "gateway": "10.11.200.1",
                    "dns": ["1.1.1.1", "9.9.9.9"],
                },
                "vlan10": {
                    "role": "routed",
                    "enabled": True,
                    "address": "192.168.10.1/24",
                },
            },
            "static_routes": [
                {
                    "destination": "192.168.50.0/24",
                    "via": "10.11.200.1",
                    "interface": "mgmt0",
                    "metric": 100,
                    "enabled": True,
                }
            ],
        }
    )

    rendered = generate_netplan(config)

    assert "mgmt0:" in rendered
    assert "vlan10:" in rendered
    assert "to: default" in rendered
    assert "via: 10.11.200.1" in rendered
    assert "to: 192.168.50.0/24" in rendered
    assert "renderer: networkd" in rendered
