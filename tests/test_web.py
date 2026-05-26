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
