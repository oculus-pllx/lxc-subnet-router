from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_install_script_accepts_noninteractive_admin_credentials():
    text = (ROOT / "install.sh").read_text(encoding="utf-8")

    assert "LXC_SUBNET_ROUTER_ADMIN_USER" in text
    assert "LXC_SUBNET_ROUTER_ADMIN_PASSWORD" in text
    assert "set-user \"$ADMIN_USER\" --group admin" in text
    assert "set-user admin --disabled" in text
