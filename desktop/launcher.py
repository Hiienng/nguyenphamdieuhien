"""
Getify desktop launcher.

Starts the FastAPI/uvicorn server on a local port in a background thread, then
opens a native window (pywebview) pointing at it. No browser, no domain — the
user just double-clicks the app. The bundled .env still points DATABASE_URL at
the cloud Neon DB, so an internet connection is required.
"""
import os
import sys
import socket
import threading
import time
import urllib.request
from pathlib import Path


def _base_dir() -> Path:
    """Resource root holding frontend/, docs/, extension files and .env."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    # dev: desktop/ is a sibling of backend/ and frontend/
    return Path(__file__).resolve().parents[1]


BASE = _base_dir()
# Make the backend find bundled static dirs + .env, and run in production mode.
os.environ.setdefault("ETSY_RESOURCE_ROOT", str(BASE))
os.environ.setdefault("APP_ENV", "production")

# In dev (not frozen) the `app` package lives under backend/.
if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(BASE / "backend"))


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


def main() -> None:
    import uvicorn
    from app.main import app  # imported after env vars are set

    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{port}/"
    ready = _wait_until_ready(base_url + "health")
    if not ready:
        sys.stderr.write("Server failed to start within timeout.\n")

    # Headless self-test (used by build verification / CI smoke test):
    # start the server, confirm it serves, then exit without opening a window.
    if os.environ.get("GETIFY_HEADLESS") == "1":
        print("GETIFY_HEADLESS ok=" + ("1" if ready else "0") + " url=" + base_url)
        server.should_exit = True
        return

    import webview  # pywebview

    webview.create_window(
        "GetifyCo Listing Portal",
        base_url,
        width=1280,
        height=860,
        min_size=(1024, 680),
    )
    webview.start()

    # Window closed -> shut the server down and exit.
    server.should_exit = True


if __name__ == "__main__":
    main()
