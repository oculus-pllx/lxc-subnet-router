# MVP Router Manager Implementation Plan

> Implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a usable MVP with config validation, Netplan generation, CLI recovery, installer, and a minimal FastAPI management UI.

**Architecture:** Keep system-changing behavior behind a small Python core module that can run in dry-run tests and from both CLI and web routes. The CLI and FastAPI app share the same config, auth, interface, route, and apply services.

**Tech Stack:** Python 3.10+, FastAPI, Jinja2, PyYAML, pytest, argparse, systemd, Netplan, iproute2.

---

### Task 1: Project Skeleton And Tests

**Files:**
- Create: `pyproject.toml`
- Create: `requirements.txt`
- Create: `src/lxc_subnet_router/`
- Create: `tests/`

- [x] Write failing import/version tests.
- [x] Run `pytest` and confirm import failures.
- [x] Add package skeleton and dependencies.
- [x] Run `pytest` and confirm pass.

### Task 2: Config, Auth, And Netplan Core

**Files:**
- Create: `src/lxc_subnet_router/config.py`
- Create: `src/lxc_subnet_router/auth.py`
- Create: `src/lxc_subnet_router/netplan.py`
- Test: `tests/test_config.py`, `tests/test_auth.py`, `tests/test_netplan.py`

- [x] Write failing tests for default config, role permissions, password verification, and generated Netplan.
- [x] Run targeted tests and confirm failures.
- [x] Implement the core modules.
- [x] Run targeted tests and confirm pass.

### Task 3: System Operations And CLI

**Files:**
- Create: `src/lxc_subnet_router/system.py`
- Create: `src/lxc_subnet_router/cli.py`
- Test: `tests/test_system.py`, `tests/test_cli.py`

- [x] Write failing tests for interface parsing, route parsing, preview, and CLI status behavior.
- [x] Run targeted tests and confirm failures.
- [x] Implement dry-run friendly system operations and argparse CLI.
- [x] Run targeted tests and confirm pass.

### Task 4: Web UI And Installer

**Files:**
- Create: `src/lxc_subnet_router/web.py`
- Create: `src/lxc_subnet_router/templates/*.html`
- Create: `install.sh`
- Create: `README.md`
- Test: `tests/test_web.py`

- [x] Write failing FastAPI smoke tests.
- [x] Run targeted tests and confirm failures.
- [x] Implement minimal authenticated dashboard, interfaces, routes, users, preview, apply, rollback pages.
- [x] Add installer and README.
- [x] Run tests and syntax checks.

### Task 5: Final Verification And Commit

- [x] Run `pytest`.
- [x] Run CLI smoke commands.
- [x] Review git diff.
- [x] Commit and push MVP.
