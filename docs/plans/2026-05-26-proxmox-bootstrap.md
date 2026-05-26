# Proxmox Bootstrap Implementation Plan

> Implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a one-line Proxmox node bootstrapper that creates an LXC, attaches management and routed interfaces, installs the app, and seeds initial config.

**Architecture:** The host script owns Proxmox orchestration only: template resolution, `pct create`, network attachment, container start, repo install, and CLI seeding. The app remains the owner of in-container IP addressing through its existing CLI and Netplan generation.

**Tech Stack:** Bash, Proxmox `pct`/`pveam`/`pvesh`/`pvesm`, existing Python CLI, static pytest checks.

---

### Task 1: Static Bootstrap Tests

**Files:**
- Create: `tests/test_bootstrap_static.py`

- [x] Write tests asserting the bootstrap script has Proxmox preflight checks, OS choices, privileged LXC creation, app-owned `ip=manual` interfaces, admin credential prompts, variable routed interface questionnaire, and in-container CLI seeding.
- [x] Run tests and confirm they fail because the script does not exist.

### Task 2: Host Bootstrap Script

**Files:**
- Create: `lxc-subnet-router-bootstrap.sh`

- [x] Implement helper functions, prompts, template resolution, storage detection, network interface questionnaire, container creation, app install, and summary output.
- [x] Run static tests and shell syntax checks.

### Task 3: Documentation

**Files:**
- Modify: `README.md`

- [x] Add the one-line Proxmox install command.
- [x] Document the questionnaire fields and interface ownership model.
- [x] Run the full test suite.

### Task 4: Commit

- [x] Run `pytest`, `compileall`, and `bash -n` checks.
- [x] Commit and push.
