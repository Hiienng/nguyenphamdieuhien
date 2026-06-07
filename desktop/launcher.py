"""
GetifyCo Listing Portal — desktop launcher.

Starts the FastAPI/uvicorn server on a local port and opens it in a native
window (pywebview). No browser, no domain. An internet connection is required
(the DB is cloud Postgres / Neon).

Config resolution (highest priority first):
  1. ~/.getifyco-listing-portal/config.env   — user override (written by Settings)
  2. <bundle>/app_config.env                 — baked default (private CI build)
  3. first-run setup screen                  — asks DB URL + token, saves to (1)

Public builds ship WITHOUT app_config.env (no secrets). The private build bakes
DATABASE_URL + SECRET_KEY into app_config.env so the app works out of the box.
"""
import os
import sys
import socket
import threading
import time
import urllib.request
from pathlib import Path


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parents[1]


BASE = _base_dir()
os.environ.setdefault("ETSY_RESOURCE_ROOT", str(BASE))
os.environ.setdefault("APP_ENV", "production")
# Desktop mode: server is local + single-user, so the login screen is skipped
# (the backend trusts localhost and the portal opens straight to /app).
os.environ.setdefault("DESKTOP_MODE", "1")

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(BASE / "backend"))

CONFIG_DIR = Path.home() / ".getifyco-listing-portal"
USER_CONFIG = CONFIG_DIR / "config.env"
BUNDLED_CONFIG = BASE / "app_config.env"

_server = None


# ── config ──────────────────────────────────────────────────────────────────
def _load_env_file(path: Path) -> dict:
    cfg = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            cfg[k.strip()] = v.strip()
    return cfg


def _effective_config() -> dict:
    cfg = {}
    cfg.update(_load_env_file(BUNDLED_CONFIG))   # baked default (private build)
    cfg.update(_load_env_file(USER_CONFIG))      # user override wins
    return cfg


def _is_configured() -> bool:
    cfg = _effective_config()
    return bool(cfg.get("DATABASE_URL") and cfg.get("SECRET_KEY"))


def _apply_config() -> None:
    for k, v in _effective_config().items():
        if v:
            os.environ[k] = v


def _write_user_config(db_url: str, market_db: str, secret: str) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    lines = [f"DATABASE_URL={db_url}", f"SECRET_KEY={secret}"]
    if market_db:
        lines.append(f"ETSY_MARKET_DB={market_db}")
    USER_CONFIG.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        os.chmod(USER_CONFIG, 0o600)
    except Exception:
        pass


# ── server ──────────────────────────────────────────────────────────────────
def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _wait_until_ready(url: str, timeout: float = 40.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.5):
                return True
        except Exception:
            time.sleep(0.3)
    return False


def _start_server() -> str:
    global _server
    import uvicorn
    from app.main import app  # imported AFTER config env vars are set

    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    _server = uvicorn.Server(config)
    threading.Thread(target=_server.run, daemon=True).start()
    base_url = f"http://127.0.0.1:{port}/"
    _wait_until_ready(base_url + "health")
    return base_url


# ── first-run setup bridge ────────────────────────────────────────────────────
class SetupApi:
    """Exposed to the first-run setup page as window.pywebview.api."""

    def __init__(self):
        self.window = None

    def save_config(self, db_url, market_db, secret):
        db_url = (db_url or "").strip()
        secret = (secret or "").strip()
        market_db = (market_db or "").strip()
        if not db_url or not secret:
            return {"ok": False, "error": "Cần nhập Database URL và Access token."}
        try:
            _write_user_config(db_url, market_db, secret)
            _apply_config()
            url = _start_server()
            self.window.load_url(url + "app")
            return {"ok": True}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": str(e)}


def main() -> None:
    headless = os.environ.get("GETIFY_HEADLESS") == "1"

    if _is_configured():
        _apply_config()
        url = _start_server()
        if headless:
            print("GETIFY_HEADLESS ok=1 url=" + url)
            if _server:
                _server.should_exit = True
            return
        import webview
        webview.create_window(
            "GetifyCo Listing Portal", url + "app",
            width=1280, height=860, min_size=(1024, 680),
        )
    else:
        if headless:
            print("GETIFY_HEADLESS ok=setup-needed")
            return
        import webview
        setup_html = (BASE / "frontend" / "setup.html").read_text(encoding="utf-8")
        api = SetupApi()
        win = webview.create_window(
            "GetifyCo Listing Portal — Cấu hình", html=setup_html,
            js_api=api, width=720, height=760,
        )
        api.window = win

    webview.start()
    if _server:
        _server.should_exit = True


if __name__ == "__main__":
    main()
