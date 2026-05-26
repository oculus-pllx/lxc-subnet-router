from fastapi.testclient import TestClient

from lxc_subnet_router.config import RouterConfig, default_config
from lxc_subnet_router.web import create_app


def test_dashboard_redirects_to_login_when_auth_enabled(tmp_path):
    config_path = tmp_path / "router.yaml"
    config = default_config(["mgmt0"])
    config["auth"]["enabled"] = True
    config["users"]["admin"] = {"enabled": True, "group": "admin", "password_hash": "unused"}
    RouterConfig.from_dict(config).save(config_path)

    client = TestClient(create_app(config_path=config_path))
    response = client.get("/", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_dashboard_renders_when_auth_disabled(tmp_path):
    config_path = tmp_path / "router.yaml"
    config = default_config(["mgmt0"])
    config["auth"]["enabled"] = False
    RouterConfig.from_dict(config).save(config_path)

    client = TestClient(create_app(config_path=config_path))
    response = client.get("/")

    assert response.status_code == 200
    assert "LXC Subnet Router" in response.text
    assert 'data-theme="dark"' in response.text
    assert "Wizard" in response.text


def test_preview_renders_netplan_when_auth_disabled(tmp_path):
    config_path = tmp_path / "router.yaml"
    config = default_config(["mgmt0"])
    config["auth"]["enabled"] = False
    config["interfaces"]["mgmt0"]["address"] = "10.0.0.2/24"
    RouterConfig.from_dict(config).save(config_path)

    client = TestClient(create_app(config_path=config_path))
    response = client.get("/preview")

    assert response.status_code == 200
    assert "mgmt0:" in response.text
    assert "10.0.0.2/24" in response.text


def test_wizard_saves_management_and_routed_interfaces_without_coupling(tmp_path):
    config_path = tmp_path / "router.yaml"
    config = default_config(["mgmt0", "vlan10", "vlan20"])
    config["auth"]["enabled"] = False
    RouterConfig.from_dict(config).save(config_path)

    client = TestClient(create_app(config_path=config_path))
    response = client.post(
        "/wizard",
        data={
            "management_name": "mgmt0",
            "management_address": "10.11.200.68/24",
            "management_gateway": "10.11.200.1",
            "management_dns": "1.1.1.1,9.9.9.9",
            "routed_name": ["vlan10", "vlan20"],
            "routed_address": ["192.168.10.1/24", "192.168.20.1/24"],
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    saved = RouterConfig.load(config_path).data
    assert saved["interfaces"]["mgmt0"]["role"] == "management"
    assert saved["interfaces"]["mgmt0"]["address"] == "10.11.200.68/24"
    assert saved["interfaces"]["vlan10"]["role"] == "routed"
    assert saved["interfaces"]["vlan10"]["address"] == "192.168.10.1/24"
    assert saved["interfaces"]["vlan20"]["role"] == "routed"
    assert saved["interfaces"]["vlan20"]["address"] == "192.168.20.1/24"
    assert saved["static_routes"] == []
