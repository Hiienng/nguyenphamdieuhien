# GetifyCo Listing Portal — Desktop App

Click-to-run desktop build of the Listing Manager portal. It starts the FastAPI
server **locally on the user's machine** and opens it in a native window (via
[pywebview](https://pywebview.flowlib.org/)) — **no domain / no Render**. An
**internet connection is required** (the DB is cloud Postgres / Neon). Login uses
the `SECRET_KEY` access token.

## Config resolution (no secrets in public builds)

The app reads its DB config in this order (highest priority first):

1. `~/.getifyco-listing-portal/config.env` — per-user override, written by the
   in-app **Settings** screen (and by first-run setup).
2. `<bundle>/app_config.env` — baked default, present **only in the private
   build** (see below).
3. **First-run setup screen** — if neither exists, the app asks for the Database
   URL + access token and saves them to (1).

So **public builds ship with no credentials**; the **private build** bakes
`DATABASE_URL` + `SECRET_KEY` so it works out of the box.

## What's inside

| File | Purpose |
|------|---------|
| `launcher.py` | Resolves config, boots uvicorn on a free localhost port, opens the window (or the first-run setup window). |
| `Getify.spec` | PyInstaller spec — bundles `app`, `frontend/`, `docs/`, the extension asset, and `app_config.env` **if present**. |
| `requirements-desktop.txt` | Backend runtime + `pywebview` + `pyinstaller`. |
| `build.sh` / `build.ps1` | One-shot local build (macOS / Windows). |

## Two build flavors

- **Public build (BYO config)** — built from this public repo with no
  `app_config.env`. First run shows the setup screen. Safe to distribute openly.
  Build locally: `cd desktop && PYTHON=python3 ./build.sh` (mac) /
  `powershell -ExecutionPolicy Bypass -File build.ps1` (win).
- **Private build (DB bundled)** — built by the **private repo**
  `Hiienng/getifyco-listing-portal`. Its workflow checks out this public code,
  writes `app_config.env` from the repo's Actions secrets (`DATABASE_URL`,
  `SECRET_KEY`, `ETSY_MARKET_DB`), builds macOS + Windows, and publishes a
  **private Release**. Trigger by pushing a tag `v*` in that repo. Because the
  release is private, the bundled credentials never go public.

## Run / verify

- Double-click `getifyco-listing-portal.app` (macOS) / `getifyco-listing-portal.exe` (Windows).
- Change the database later via the app's **Settings** link (restart to apply).
- Headless smoke test (no window):
  ```bash
  GETIFY_HEADLESS=1 ./dist/getifyco-listing-portal.app/Contents/MacOS/getifyco-listing-portal
  # prints "GETIFY_HEADLESS ok=1" (configured) or "ok=setup-needed" (no config)
  ```

## Notes

- Windows uses the Edge **WebView2** runtime (preinstalled on Windows 10/11).
- macOS/Windows builds are unsigned → first launch: right-click → Open (mac, or
  `xattr -dr com.apple.quarantine getifyco-listing-portal.app`) / More info → Run
  anyway (win). Sign & notarize for friction-free distribution.
- macOS CI runners are Apple Silicon → the released `.app` is arm64. Intel Macs
  need an `x86_64`/universal build (`macos-13` runner).
- `google-generativeai` is excluded from the bundle (optional title
  classification only); imported lazily and skipped if absent.
