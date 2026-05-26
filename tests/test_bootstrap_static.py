from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = ROOT / "lxc-subnet-router-bootstrap.sh"


def script_text() -> str:
    return BOOTSTRAP.read_text(encoding="utf-8")


def test_bootstrap_script_exists_and_has_one_line_url():
    text = script_text()

    assert "bash <(curl -fsSL https://raw.githubusercontent.com/oculus-pllx/lxc-subnet-router/main/lxc-subnet-router-bootstrap.sh)" in text


def test_bootstrap_checks_proxmox_commands_and_os_templates():
    text = script_text()

    for command in ("pct", "pveam", "pvesh", "pvesm"):
        assert f"command -v {command}" in text
    assert "ubuntu-24\\.04-standard" in text
    assert "ubuntu-26\\.04-standard" in text
    assert "debian-13-standard" in text


def test_bootstrap_creates_privileged_lxc_with_manual_app_owned_interfaces():
    text = script_text()

    assert "--unprivileged 0" in text
    assert "--features" in text
    assert "nesting=1,keyctl=1" in text
    assert "name=mgmt0" in text
    assert "ip=manual" in text
    assert "pct set \"$CT_ID\" --net" in text


def test_bootstrap_questionnaire_supports_variable_named_routed_interfaces():
    text = script_text()

    assert "How many additional routed interfaces" in text
    assert "Interface name" in text
    assert "Subnet gateway CIDR" in text
    assert "Bridge" in text
    assert "DHCP/manual" in text


def test_bootstrap_discovers_proxmox_bridges_and_sdn_vnets_for_selection():
    text = script_text()

    assert "discover_networks" in text
    assert 'pvesh get /nodes/"$node_name"/network' in text
    assert "pvesh get /cluster/sdn/vnets" in text
    assert "Available Proxmox bridges and SDN VNets" in text
    assert "select_network" in text
    assert "Enter a number or network name" in text
    assert "Invalid Proxmox bridge or SDN VNet name." in text


def test_bootstrap_seeds_app_credentials_and_cli_config_inside_container():
    text = script_text()

    assert "Router admin username" in text
    assert "Router admin password" in text
    assert "lxc-subnet-router --config" in text
    assert "set-interface mgmt0 --role management" in text
    assert "${iface_name}" in text
    assert "set-user '$ROUTER_ADMIN_USER' --group admin" in text
    assert "verify-login '$ROUTER_ADMIN_USER' --password-env ROUTER_PASSWORD" in text
    assert "LXC_SUBNET_ROUTER_SKIP_ADMIN=1" in text
    assert "systemctl restart lxc-subnet-router.service" in text
    assert "Router web UI login set to ${ROUTER_ADMIN_USER}." in text
    assert "prepare_container_network" in text
    assert "dhcp4: true" in text
    assert "--dhcp --enabled" in text
    assert "--role routed --manual --enabled" in text


def test_bootstrap_reprompts_bad_questionnaire_entries_and_normalizes_modes():
    text = script_text()

    assert "read_valid" in text
    assert "read_ipv4_cidr_or_mode" in text
    assert "read_resource_number" in text
    assert 'CT_SWAP="${CT_SWAP:-$CT_RAM}"' in text
    assert 'mode=$(printf' in text
    assert "tr '[:upper:]' '[:lower:]'" in text
    assert "warn \"Use static, dhcp, or manual.\"" in text
    assert "continue" in text


def test_bootstrap_secret_and_warning_output_do_not_pollute_captured_answers():
    text = script_text()

    assert 'echo "" >&2' in text
    assert 'warn() { echo -e "${YELLOW}[WARN]${NC} $*" >&2; }' in text


def test_bootstrap_and_installer_disable_ipv6_completely():
    bootstrap = script_text()
    installer = (ROOT / "install.sh").read_text(encoding="utf-8")

    for text in (bootstrap, installer):
        assert "net.ipv6.conf.all.disable_ipv6=1" in text
        assert "net.ipv6.conf.default.disable_ipv6=1" in text
        assert "net.ipv6.conf.lo.disable_ipv6=1" in text
