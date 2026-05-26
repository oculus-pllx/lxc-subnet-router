#!/usr/bin/env bash
# LXC Subnet Router Proxmox bootstrapper
#
# One-line install from a Proxmox node shell:
#   bash <(curl -fsSL https://raw.githubusercontent.com/oculus-pllx/lxc-subnet-router/main/lxc-subnet-router-bootstrap.sh)
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

REPO_URL="${REPO_URL:-https://github.com/oculus-pllx/lxc-subnet-router.git}"
RAW_BASE="${RAW_BASE:-https://raw.githubusercontent.com/oculus-pllx/lxc-subnet-router/main}"
APP_CONFIG=/opt/lxc-subnet-router/config/router.yaml

CT_ID=""
CT_HOSTNAME=""
CT_PASSWORD=""
CT_CORES=""
CT_RAM=""
CT_SWAP=""
CT_DISK=""
CT_STORAGE=""
CT_OSTYPE=""
CT_OS_LABEL=""
TEMPLATE=""
TEMPLATE_PATH=""
MGMT_BRIDGE=""
MGMT_ADDRESS=""
MGMT_GATEWAY=""
MGMT_DNS=""
ROUTER_ADMIN_USER=""
ROUTER_ADMIN_PASSWORD=""
ROUTED_COUNT=0

ROUTED_NAMES=()
ROUTED_BRIDGES=()
ROUTED_MODES=()
ROUTED_ADDRESSES=()
AVAILABLE_NETWORKS=()

info() { echo -e "${CYAN}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }

header() {
  echo ""
  echo -e "${BOLD}LXC Subnet Router Bootstrap${NC}"
  echo "Creates a Proxmox LXC and installs the subnet router manager."
  echo ""
}

preflight() {
  [[ "$(id -u)" -eq 0 ]] || error "Run this as root on the Proxmox node."
  command -v pct >/dev/null 2>&1 || error "pct not found. Run this on a Proxmox node."
  command -v pveam >/dev/null 2>&1 || error "pveam not found. Run this on a Proxmox node."
  command -v pvesh >/dev/null 2>&1 || error "pvesh not found. Run this on a Proxmox node."
  command -v pvesm >/dev/null 2>&1 || error "pvesm not found. Run this on a Proxmox node."
  command -v curl >/dev/null 2>&1 || error "curl is required on the Proxmox node."
}

valid_name() {
  [[ "$1" =~ ^[a-zA-Z0-9_.:-]+$ ]]
}

valid_iface() {
  [[ "$1" =~ ^[a-zA-Z][a-zA-Z0-9_.:-]{0,14}$ ]]
}

read_required_secret() {
  local prompt=$1
  local value=""
  while [[ -z "$value" ]]; do
    read -rsp "$prompt" value
    echo ""
    [[ -n "$value" ]] || warn "Value cannot be empty."
  done
  printf '%s\n' "$value"
}

read_valid() {
  local prompt=$1
  local default_value=$2
  local validator=$3
  local message=$4
  local value
  while true; do
    read -rp "$prompt [$default_value]: " value
    value="${value:-$default_value}"
    if "$validator" "$value"; then
      printf '%s\n' "$value"
      return 0
    fi
    warn "$message"
  done
}

valid_number() {
  [[ "$1" =~ ^[0-9]+$ ]]
}

valid_admin_username() {
  [[ "$1" =~ ^[a-z_][a-z0-9_-]*$ ]]
}

valid_ipv4() {
  [[ "$1" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]
}

valid_ipv4_cidr() {
  [[ "$1" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+/[0-9]+$ ]]
}

valid_dns_list() {
  [[ "$1" =~ ^[0-9.,[:space:]]+$ ]]
}

valid_management_address() {
  local value
  value=$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')
  [[ -z "$value" || "$value" == "dhcp" || "$value" == "manual" || "$value" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+/[0-9]+$ ]]
}

read_resource_number() {
  read_valid "$1" "$2" valid_number "$1 must be numeric."
}

read_ipv4_cidr_or_mode() {
  local value
  while true; do
    read -rp "$1 [$2]: " value
    value="${value:-$2}"
    value=$(printf '%s' "$value" | tr '[:upper:]' '[:lower:]')
    if valid_management_address "$value"; then
      printf '%s\n' "$value"
      return 0
    fi
    warn "$1 must be dhcp/manual or IPv4 CIDR."
  done
}

read_routed_mode() {
  local mode
  while true; do
    read -rp "DHCP/manual or static? [static]: " mode
    mode="${mode:-static}"
    mode=$(printf '%s' "$mode" | tr '[:upper:]' '[:lower:]')
    case "$mode" in
      static|dhcp|manual)
        printf '%s\n' "$mode"
        return 0
        ;;
      *)
        warn "Use static, dhcp, or manual."
        continue
        ;;
    esac
  done
}

choose_os() {
  echo -e "${BOLD}OS Template${NC}"
  echo "  1) Ubuntu 24.04 LTS (default)"
  echo "  2) Ubuntu 26.04 LTS"
  echo "  3) Debian 13 latest"
  read -rp "OS [1]: " os_choice
  os_choice="${os_choice:-1}"

  case "$os_choice" in
    2)
      CT_OSTYPE="ubuntu"
      CT_OS_LABEL="Ubuntu 26.04 LTS"
      template_pattern='^ubuntu-26\.04-standard_26\.04-[0-9]+_amd64\.tar\.zst$'
      ;;
    3)
      CT_OSTYPE="debian"
      CT_OS_LABEL="Debian 13 latest"
      template_pattern='^debian-13-standard_13\.[0-9]+-[0-9]+_amd64\.tar\.zst$'
      ;;
    *)
      CT_OSTYPE="ubuntu"
      CT_OS_LABEL="Ubuntu 24.04 LTS"
      template_pattern='^ubuntu-24\.04-standard_24\.04-[0-9]+_amd64\.tar\.zst$'
      ;;
  esac

  TEMPLATE=$(pveam available --section system 2>/dev/null | awk '{print $2}' | grep -E "$template_pattern" | sort -V | tail -1)
  if [[ -z "$TEMPLATE" ]]; then
    warn "$CT_OS_LABEL template not found in local index. Running pveam update ..."
    pveam update >/dev/null 2>&1 || true
    TEMPLATE=$(pveam available --section system 2>/dev/null | awk '{print $2}' | grep -E "$template_pattern" | sort -V | tail -1)
  fi
  [[ -n "$TEMPLATE" ]] || error "$CT_OS_LABEL LXC template not found."
}

detect_storage() {
  local storage_list
  storage_list=$(pvesm status --content rootdir 2>/dev/null | awk 'NR>1 && $2=="active" {print $1}' | sort)
  if echo "$storage_list" | grep -qx "local-lvm"; then
    printf '%s\n' "local-lvm"
  elif [[ -n "$storage_list" ]]; then
    echo "$storage_list" | head -1
  else
    printf '%s\n' "local-lvm"
  fi
}

discover_networks() {
  local node_name bridges vnets combined
  node_name=$(hostname)
  bridges=$(pvesh get /nodes/"$node_name"/network --output-format json 2>/dev/null \
    | grep -o '"iface":"[^"]*"' \
    | cut -d'"' -f4 \
    | grep -E '^(vmbr|br)[a-zA-Z0-9_.:-]*$' || true)
  vnets=$(pvesh get /cluster/sdn/vnets --output-format json 2>/dev/null \
    | grep -Eo '"(vnet|vnetid)":"[^"]*"' \
    | cut -d'"' -f4 || true)
  combined=$(printf '%s\n%s\n' "$bridges" "$vnets" | sed '/^$/d' | sort -u)
  if [[ -z "$combined" ]]; then
    combined="vmbr0"
  fi
  mapfile -t AVAILABLE_NETWORKS <<<"$combined"
}

select_network() {
  local prompt=$1
  local default_value=$2
  local choice selected

  while true; do
    echo "Available Proxmox bridges and SDN VNets:" >&2
    local index=1
    for network in "${AVAILABLE_NETWORKS[@]}"; do
      echo "  ${index}) ${network}" >&2
      index=$((index + 1))
    done
    echo "Enter a number or network name. Manual entries are allowed." >&2

    read -rp "$prompt [$default_value]: " choice
    choice="${choice:-$default_value}"
    if [[ "$choice" =~ ^[0-9]+$ ]] && (( choice >= 1 && choice <= ${#AVAILABLE_NETWORKS[@]} )); then
      selected="${AVAILABLE_NETWORKS[$((choice - 1))]}"
    else
      selected="$choice"
    fi
    if valid_name "$selected"; then
      printf '%s\n' "$selected"
      return 0
    fi
    warn "Invalid Proxmox bridge or SDN VNet name."
  done
}

get_config() {
  local next_id default_storage
  next_id=$(pvesh get /cluster/nextid 2>/dev/null || echo "100")
  default_storage=$(detect_storage)
  discover_networks

  choose_os

  while true; do
    CT_ID=$(read_valid "Container ID" "$next_id" valid_number "Container ID must be numeric.")
    if pct status "$CT_ID" >/dev/null 2>&1; then
      warn "Container ID $CT_ID already exists."
      continue
    fi
    break
  done

  CT_HOSTNAME=$(read_valid "Hostname" "lxc-subnet-router" valid_name "Invalid hostname.")

  CT_PASSWORD=$(read_required_secret "Container root password: ")

  CT_CORES=$(read_resource_number "CPU cores" "2")
  CT_RAM=$(read_resource_number "RAM in MB" "1024")
  read -rp "Swap in MB [$CT_RAM]: " CT_SWAP
  CT_SWAP="${CT_SWAP:-$CT_RAM}"
  while ! valid_number "$CT_SWAP"; do
    warn "Swap in MB must be numeric."
    read -rp "Swap in MB [$CT_RAM]: " CT_SWAP
    CT_SWAP="${CT_SWAP:-$CT_RAM}"
  done
  CT_DISK=$(read_resource_number "Disk size in GB" "8")
  CT_STORAGE=$(read_valid "Storage" "$default_storage" valid_name "Invalid storage name.")

  echo ""
  echo -e "${BOLD}Router Admin${NC}"
  ROUTER_ADMIN_USER=$(read_valid "Router admin username" "admin" valid_admin_username "Invalid admin username.")
  ROUTER_ADMIN_PASSWORD=$(read_required_secret "Router admin password: ")

  echo ""
  echo -e "${BOLD}Management Interface${NC}"
  MGMT_BRIDGE=$(select_network "Management bridge or SDN VNet" "vmbr0")
  MGMT_ADDRESS=$(read_ipv4_cidr_or_mode "Management IP/CIDR" "manual")
  if [[ -n "$MGMT_ADDRESS" && "$MGMT_ADDRESS" != "dhcp" && "$MGMT_ADDRESS" != "manual" ]]; then
    MGMT_GATEWAY=$(read_valid "Management gateway" "" valid_ipv4 "Management gateway must be a plain IPv4 address.")
  fi
  MGMT_DNS=$(read_valid "Management DNS" "1.1.1.1,9.9.9.9" valid_dns_list "Management DNS must be comma-separated IPv4 addresses.")

  echo ""
  echo -e "${BOLD}Routed Interfaces${NC}"
  ROUTED_COUNT=$(read_resource_number "How many additional routed interfaces?" "2")

  for ((i = 1; i <= ROUTED_COUNT; i++)); do
    local default_name default_bridge iface_name bridge mode address
    default_name="vlan$((i * 10))"
    default_bridge="vmbr$((i * 10))"
    echo ""
    echo "Additional interface $i"
    while true; do
      iface_name=$(read_valid "Interface name" "$default_name" valid_iface "Invalid interface name.")
      if [[ "$iface_name" == "mgmt0" ]]; then
        warn "Additional routed interface cannot be mgmt0."
        continue
      fi
      break
    done
    bridge=$(select_network "Bridge or SDN VNet" "$default_bridge")
    mode=$(read_routed_mode)
    case "$mode" in
      static)
        address=$(read_valid "Subnet gateway CIDR for $iface_name" "192.168.$((i * 10)).1/24" valid_ipv4_cidr "Subnet gateway CIDR must be an IPv4 CIDR.")
        ;;
      dhcp|manual)
        address=""
        ;;
    esac
    ROUTED_NAMES+=("$iface_name")
    ROUTED_BRIDGES+=("$bridge")
    ROUTED_MODES+=("$mode")
    ROUTED_ADDRESSES+=("$address")
  done

  echo ""
  echo -e "${BOLD}Summary${NC}"
  echo "  OS:              $CT_OS_LABEL"
  echo "  CT:              $CT_ID ($CT_HOSTNAME)"
  echo "  Resources:       $CT_CORES vCPU / ${CT_RAM}MB RAM / ${CT_DISK}GB disk"
  echo "  Storage:         $CT_STORAGE"
  echo "  mgmt0:           bridge=$MGMT_BRIDGE app-address=${MGMT_ADDRESS:-manual}"
  echo "  routed count:    $ROUTED_COUNT"
  for ((i = 0; i < ROUTED_COUNT; i++)); do
    echo "  ${ROUTED_NAMES[$i]}:          bridge=${ROUTED_BRIDGES[$i]} mode=${ROUTED_MODES[$i]} address=${ROUTED_ADDRESSES[$i]:-manual}"
  done
  echo "  Web UI:          0.0.0.0:8443"
  echo ""
  read -rp "Proceed? (y/N): " confirm
  [[ "$confirm" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 0; }
}

get_template() {
  info "Checking for template: $TEMPLATE"
  if ! pveam list local 2>/dev/null | grep -q "$TEMPLATE"; then
    info "Downloading $TEMPLATE ..."
    pveam download local "$TEMPLATE" || error "Template download failed."
  fi
  TEMPLATE_PATH="local:vztmpl/$TEMPLATE"
}

create_container() {
  info "Creating privileged LXC $CT_ID ..."
  pct create "$CT_ID" "$TEMPLATE_PATH" \
    --hostname "$CT_HOSTNAME" \
    --password "$CT_PASSWORD" \
    --cores "$CT_CORES" \
    --memory "$CT_RAM" \
    --swap "$CT_SWAP" \
    --rootfs "$CT_STORAGE:$CT_DISK" \
    --net0 "name=mgmt0,bridge=$MGMT_BRIDGE,ip=manual" \
    --nameserver "1.1.1.1" \
    --ostype "$CT_OSTYPE" \
    --unprivileged 0 \
    --features nesting=1,keyctl=1 \
    --onboot 1 \
    --start 0

  for ((i = 0; i < ROUTED_COUNT; i++)); do
    local net_index=$((i + 1))
    pct set "$CT_ID" --net"${net_index}" "name=${ROUTED_NAMES[$i]},bridge=${ROUTED_BRIDGES[$i]},ip=manual"
  done
  success "Container $CT_ID created."
}

start_container() {
  info "Starting container $CT_ID ..."
  pct start "$CT_ID"
  local attempts=0
  until [[ "$(pct status "$CT_ID" 2>/dev/null | awk '{print $2}')" == "running" ]]; do
    attempts=$((attempts + 1))
    [[ "$attempts" -lt 60 ]] || error "Container did not start after 120 seconds."
    sleep 2
  done
  sleep 5
}

prepare_container_network() {
  info "Preparing temporary container management networking ..."
  pct exec "$CT_ID" -- ip link set mgmt0 up || true
  if [[ -n "$MGMT_ADDRESS" && "$MGMT_ADDRESS" != "dhcp" && "$MGMT_ADDRESS" != "manual" ]]; then
    pct exec "$CT_ID" -- ip addr flush dev mgmt0 || true
    pct exec "$CT_ID" -- ip addr add "$MGMT_ADDRESS" dev mgmt0
    pct exec "$CT_ID" -- ip route replace default via "$MGMT_GATEWAY" dev mgmt0
    pct exec "$CT_ID" -- env BOOTSTRAP_DNS="${MGMT_DNS%%,*}" bash -lc 'printf "nameserver %s\n" "$BOOTSTRAP_DNS" > /etc/resolv.conf'
  elif [[ "$MGMT_ADDRESS" == "dhcp" ]]; then
    pct exec "$CT_ID" -- bash -lc "cat >/etc/netplan/00-bootstrap-dhcp.yaml <<'NETPLAN'
network:
  version: 2
  renderer: networkd
  ethernets:
    mgmt0:
      dhcp4: true
NETPLAN
netplan generate && netplan apply"
  else
    warn "Management networking is manual with no address. The app install requires internet access; configure networking from the console if package install fails."
  fi
}

install_app() {
  info "Installing app inside container ..."
  pct exec "$CT_ID" -- bash -lc "apt-get update && apt-get install -y git curl"
  pct exec "$CT_ID" -- env REPO_URL="$REPO_URL" bash -lc 'rm -rf /opt/lxc-subnet-router-src && git clone "$REPO_URL" /opt/lxc-subnet-router-src'
  pct exec "$CT_ID" -- env LXC_SUBNET_ROUTER_ADMIN_USER="$ROUTER_ADMIN_USER" LXC_SUBNET_ROUTER_ADMIN_PASSWORD="$ROUTER_ADMIN_PASSWORD" bash -lc 'cd /opt/lxc-subnet-router-src && ./install.sh'
}

configure_app() {
  info "Configuring router app ..."
  local cli="/opt/lxc-subnet-router/venv/bin/lxc-subnet-router --config $APP_CONFIG"

  pct exec "$CT_ID" -- env ROUTER_PASSWORD="$ROUTER_ADMIN_PASSWORD" bash -lc "$cli set-user '$ROUTER_ADMIN_USER' --group admin --password-env ROUTER_PASSWORD --enabled"
  if [[ "$ROUTER_ADMIN_USER" != "admin" ]]; then
    pct exec "$CT_ID" -- bash -lc "$cli set-user admin --disabled"
  fi
  pct exec "$CT_ID" -- env ROUTER_PASSWORD="$ROUTER_ADMIN_PASSWORD" bash -lc "$cli verify-login '$ROUTER_ADMIN_USER' --password-env ROUTER_PASSWORD"

  if [[ -n "$MGMT_ADDRESS" && "$MGMT_ADDRESS" != "dhcp" && "$MGMT_ADDRESS" != "manual" ]]; then
    pct exec "$CT_ID" -- bash -lc "$cli set-interface mgmt0 --role management --address '$MGMT_ADDRESS' --gateway '$MGMT_GATEWAY' --dns '$MGMT_DNS' --enabled"
  elif [[ "$MGMT_ADDRESS" == "dhcp" ]]; then
    pct exec "$CT_ID" -- bash -lc "$cli set-interface mgmt0 --role management --dhcp --dns '$MGMT_DNS' --enabled"
  else
    pct exec "$CT_ID" -- bash -lc "$cli set-interface mgmt0 --role management --manual --enabled"
  fi

  for ((i = 0; i < ROUTED_COUNT; i++)); do
    local iface_name="${ROUTED_NAMES[$i]}"
    local iface_mode="${ROUTED_MODES[$i]}"
    local iface_address="${ROUTED_ADDRESSES[$i]}"
    if [[ -n "$iface_address" ]]; then
      pct exec "$CT_ID" -- bash -lc "$cli set-interface \"${iface_name}\" --role routed --address '$iface_address' --enabled"
    elif [[ "$iface_mode" == "dhcp" ]]; then
      pct exec "$CT_ID" -- bash -lc "$cli set-interface \"${iface_name}\" --role routed --dhcp --enabled"
    else
      pct exec "$CT_ID" -- bash -lc "$cli set-interface \"${iface_name}\" --role routed --manual --enabled"
    fi
  done
}

# IPv6 is intentionally disabled by the in-container installer and generated sysctl:
# net.ipv6.conf.all.disable_ipv6=1
# net.ipv6.conf.default.disable_ipv6=1
# net.ipv6.conf.lo.disable_ipv6=1

print_summary() {
  local ct_ip
  ct_ip=$(pct exec "$CT_ID" -- hostname -I 2>/dev/null | awk '{print $1}')
  echo ""
  success "LXC Subnet Router is ready."
  echo "  Container:      $CT_ID ($CT_HOSTNAME)"
  echo "  GUI:            http://${ct_ip:-<mgmt-ip>}:8443"
  echo "  Login:          $ROUTER_ADMIN_USER / password entered during bootstrap"
  echo "  Console:        pct enter $CT_ID"
  echo "  CLI:            pct exec $CT_ID -- /opt/lxc-subnet-router/venv/bin/lxc-subnet-router --config $APP_CONFIG status"
  echo ""
}

main() {
  header
  preflight
  get_config
  get_template
  create_container
  start_container
  prepare_container_network
  install_app
  configure_app
  print_summary
}

main "$@"
