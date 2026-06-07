# Getify Desktop App

A click-to-run desktop build of the Getify Listing Manager portal. It starts the
FastAPI server **locally on the user's machine** and opens it in a native window
(via [pywebview](https://pywebview.flowlib.org/)) — **no domain / no Render**.

The bundled `.env` still points `DATABASE_URL` at the cloud Neon database, so an
**internet connection is required**. Login uses the `SECRET_KEY` access token.

## What's inside

| File | Purpose |
|------|---------|
| `launcher.py` | Boots uvicorn on a free localhost port, then opens the pywebview window. |
| `Getify.spec` | PyInstaller spec — bundles `app`, `frontend/`, `docs/`, the extension asset and `.env`. |
| `requirements-desktop.txt` | Backend runtime + `pywebview` + `pyinstaller`. |
| `build.sh` / `build.ps1` | One-shot local build (macOS / Windows). |

## Build locally

> PyInstaller cannot cross-compile. Build the macOS `.app` on a Mac and the
> Windows `.exe` on Windows.

**macOS**
```bash
cd desktop
PYTHON=python3 ./build.sh
# -> desktop/dist/getifyco-listing-portal.app
```

**Windows**
```powershell
cd desktop
powershell -ExecutionPolicy Bypass -File build.ps1
# -> desktop\dist\getifyco-listing-portal\getifyco-listing-portal.exe
```

A `.env` in the project root is bundled automatically if present.

## Build via GitHub Actions (both OSes)

`.github/workflows/desktop-build.yml` builds macOS **and** Windows on real
runners. Trigger it by pushing a tag (`git tag v1.0.0 && git push --tags`) or via
the **Actions → Build desktop app → Run workflow** button. Artifacts
`getifyco-listing-portal-macos.zip` / `getifyco-listing-portal-windows.zip` are attached to the run.

**Required secret:** add a repo secret named **`ENV_FILE`** containing the full
contents of your `.env`. The workflow writes it to `.env` before building so the
bundled app has DB credentials. (The repo `.env` is gitignored, so CI needs this.)

## Run / verify

- Double-click `getifyco-listing-portal.app` (macOS) or `getifyco-listing-portal.exe` (Windows). A window opens on
  the login screen — paste the `SECRET_KEY` value to enter.
- Headless smoke test (no window, just confirms the embedded server boots):
  ```bash
  GETIFY_HEADLESS=1 ./dist/getifyco-listing-portal.app/Contents/MacOS/getifyco-listing-portal   # prints GETIFY_HEADLESS ok=1
  ```

## Notes

- Windows uses the Edge **WebView2** runtime (preinstalled on Windows 10/11).
- macOS builds are unsigned; on first launch use right-click → Open (or
  `xattr -dr com.apple.quarantine getifyco-listing-portal.app`) to bypass Gatekeeper. For
  distribution, sign & notarize with an Apple Developer ID.
- `google-generativeai` is intentionally excluded from the bundle (only used for
  optional title classification); it's imported lazily and skipped if absent.
