from __future__ import annotations

import secrets
import os
from pathlib import Path

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates

from lxc_subnet_router.auth import verify_password
from lxc_subnet_router.config import DEFAULT_CONFIG_PATH, RouterConfig, load_or_default
from lxc_subnet_router.netplan import generate_netplan
from lxc_subnet_router.system import apply_config, current_routes, discover_interfaces, forwarding_status


templates = Jinja2Templates(directory=str(Path(__file__).with_name("templates")))


def create_app(config_path: Path = DEFAULT_CONFIG_PATH) -> FastAPI:
    app = FastAPI(title="LXC Subnet Router")
    sessions: dict[str, str] = {}

    def load_config() -> RouterConfig:
        return load_or_default(config_path, [item["name"] for item in discover_interfaces()])

    def current_user(request: Request) -> str | None:
        config = load_config().data
        if not config.get("auth", {}).get("enabled", True):
            return "admin"
        token = request.cookies.get("lsr_session")
        if not token:
            return None
        return sessions.get(token)

    def require_user(request: Request) -> str:
        user = current_user(request)
        if not user:
            raise LoginRequired()
        return user

    def wizard_context(request: Request, user: str):
        config = load_config()
        discovered = discover_interfaces()
        names = [item["name"] for item in discovered]
        management_name = "mgmt0" if "mgmt0" in names or "mgmt0" in config.interfaces else (names[0] if names else "mgmt0")
        routed = [item for item in discovered if item["name"] != management_name and item["name"] != "lo"]
        return {
            "request": request,
            "user": user,
            "config": config.data,
            "interfaces": discovered,
            "management_name": management_name,
            "routed": routed,
        }

    @app.exception_handler(LoginRequired)
    async def login_exception_handler(request: Request, exc: LoginRequired):
        return RedirectResponse("/login", status_code=303)

    @app.get("/login", response_class=HTMLResponse)
    def login_form(request: Request):
        return templates.TemplateResponse(request, "login.html", {"error": ""})

    @app.post("/login")
    def login(request: Request, username: str = Form(...), password: str = Form(...)):
        config = load_config().data
        user = config.get("users", {}).get(username)
        if user and user.get("enabled", True) and verify_password(user.get("password_hash", ""), password):
            token = secrets.token_urlsafe(32)
            sessions[token] = username
            response = RedirectResponse("/", status_code=303)
            response.set_cookie("lsr_session", token, httponly=True, samesite="lax")
            return response
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Invalid username or password"},
            status_code=401,
        )

    @app.post("/logout")
    def logout(request: Request):
        token = request.cookies.get("lsr_session")
        if token:
            sessions.pop(token, None)
        response = RedirectResponse("/login", status_code=303)
        response.delete_cookie("lsr_session")
        return response

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request, user: str = Depends(require_user)):
        config = load_config()
        return templates.TemplateResponse(
            request,
            "dashboard.html",
            {
                "user": user,
                "config": config.data,
                "interfaces": discover_interfaces(),
                "routes": current_routes(),
                "forwarding": forwarding_status(),
            },
        )

    @app.get("/interfaces", response_class=HTMLResponse)
    def interfaces(request: Request, user: str = Depends(require_user)):
        return templates.TemplateResponse(request, "interfaces.html", {"user": user, "interfaces": discover_interfaces(), "config": load_config().data})

    @app.get("/wizard", response_class=HTMLResponse)
    def wizard(request: Request, user: str = Depends(require_user)):
        return templates.TemplateResponse(request, "wizard.html", wizard_context(request, user))

    @app.post("/wizard")
    async def save_wizard(request: Request, user: str = Depends(require_user)):
        form = await request.form()
        config = load_config()
        interfaces = config.data.setdefault("interfaces", {})
        management_name = str(form.get("management_name") or "mgmt0")
        for name, item in interfaces.items():
            if item.get("role") == "management" and name != management_name:
                item["role"] = "unused"
                item["enabled"] = False
        management = interfaces.setdefault(management_name, {})
        management["role"] = "management"
        management["enabled"] = True
        management["address"] = str(form.get("management_address") or "")
        gateway = str(form.get("management_gateway") or "")
        if gateway:
            management["gateway"] = gateway
        else:
            management.pop("gateway", None)
        dns = [entry.strip() for entry in str(form.get("management_dns") or "").split(",") if entry.strip()]
        if dns:
            management["dns"] = dns
        else:
            management.pop("dns", None)

        routed_names = form.getlist("routed_name")
        routed_addresses = form.getlist("routed_address")
        for name, address in zip(routed_names, routed_addresses):
            name = str(name).strip()
            address = str(address).strip()
            if not name or name == management_name:
                continue
            routed_interface = interfaces.setdefault(name, {})
            if address:
                routed_interface["role"] = "routed"
                routed_interface["enabled"] = True
                routed_interface["address"] = address
            else:
                routed_interface["role"] = "unused"
                routed_interface["enabled"] = False
                routed_interface["address"] = ""

        config.save(config_path)
        return RedirectResponse("/preview", status_code=303)

    @app.get("/routes", response_class=HTMLResponse)
    def routes(request: Request, user: str = Depends(require_user)):
        return templates.TemplateResponse(request, "routes.html", {"user": user, "routes": current_routes(), "config": load_config().data})

    @app.get("/users", response_class=HTMLResponse)
    def users(request: Request, user: str = Depends(require_user)):
        return templates.TemplateResponse(request, "users.html", {"user": user, "config": load_config().data})

    @app.get("/preview", response_class=HTMLResponse)
    def preview(request: Request, user: str = Depends(require_user)):
        return templates.TemplateResponse(request, "preview.html", {"user": user, "netplan": generate_netplan(load_config())})

    @app.post("/apply", response_class=HTMLResponse)
    def apply(request: Request, dry_run: bool = Form(True), user: str = Depends(require_user)):
        errors = apply_config(load_config(), dry_run=dry_run)
        return templates.TemplateResponse(request, "apply.html", {"user": user, "errors": errors, "dry_run": dry_run})

    @app.get("/health", response_class=PlainTextResponse)
    def health(user: str = Depends(require_user)):
        return f"ipv4_forwarding={forwarding_status()['ipv4']}\nroutes={len(current_routes())}\ninterfaces={len(discover_interfaces())}\n"

    return app


class LoginRequired(Exception):
    pass


app = create_app(Path(os.environ.get("LXC_SUBNET_ROUTER_CONFIG", DEFAULT_CONFIG_PATH)))
