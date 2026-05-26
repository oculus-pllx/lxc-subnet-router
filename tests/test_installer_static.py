from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_install_script_accepts_noninteractive_admin_credentials():
    text = (ROOT / "install.sh").read_text(encoding="utf-8")

    assert "LXC_SUBNET_ROUTER_ADMIN_USER" in text
    assert "LXC_SUBNET_ROUTER_ADMIN_PASSWORD" in text
    assert "set-user \"$ADMIN_USER\" --group admin" in text
    assert "set-user admin --disabled" in text


def test_install_script_can_skip_admin_creation_for_bootstrap_finalization():
    text = (ROOT / "install.sh").read_text(encoding="utf-8")

    assert "LXC_SUBNET_ROUTER_SKIP_ADMIN" in text
    assert 'if [[ "${LXC_SUBNET_ROUTER_SKIP_ADMIN:-0}" != "1" ]]' in text


def test_install_script_disables_ipv6_completely():
    text = (ROOT / "install.sh").read_text(encoding="utf-8")

    assert "net.ipv6.conf.all.disable_ipv6=1" in text
    assert "net.ipv6.conf.default.disable_ipv6=1" in text
    assert "net.ipv6.conf.lo.disable_ipv6=1" in text
