# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Getify desktop app (macOS .app + Windows .exe)."""
import os
import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files, collect_all

SPEC_DIR = os.path.abspath(SPECPATH)          # desktop/
ROOT = os.path.dirname(SPEC_DIR)              # project dir (nguyenphamdieuhien)
BACKEND = os.path.join(ROOT, "backend")

_ICNS = os.path.join(SPEC_DIR, "icon.icns")   # macOS app icon (from logo.jpg)
_ICO = os.path.join(SPEC_DIR, "icon.ico")     # Windows exe icon (from logo.jpg)
ICON_ICNS = _ICNS if os.path.exists(_ICNS) else None
ICON_ICO = _ICO if os.path.exists(_ICO) else None

# --- bundled data: static frontend, docs, extension asset, and .env ---------
datas = [
    (os.path.join(ROOT, "frontend"), "frontend"),
    # NOTE: top-level docs/ holds dev/design docs only — NOT bundled. The
    # user-facing guides live in frontend/md-docs/ (shipped via frontend above).
]
_ext = os.path.join(ROOT, "extension-keyword-main", "Archive.pxi")
if os.path.exists(_ext):
    datas.append((_ext, "extension-keyword-main"))
# Baked default config for the PRIVATE build (DATABASE_URL + SECRET_KEY). Public
# builds omit this file, so released public artifacts contain no secrets.
_appcfg = os.path.join(ROOT, "app_config.env")
if os.path.exists(_appcfg):
    datas.append((_appcfg, "."))

# CA bundle for TLS to Neon (asyncpg ssl) — without this the frozen app gets
# CERTIFICATE_VERIFY_FAILED because there is no OS trust store in the bundle.
datas += collect_data_files("certifi")

# --- hidden imports: uvicorn dynamic loaders + the backend package ----------
hiddenimports = []
hiddenimports += collect_submodules("uvicorn")
hiddenimports += collect_submodules("app")          # backend/app package
hiddenimports += [
    "asyncpg",
    "anyio",
    "httptools",
    "websockets",
    "passlib.handlers.bcrypt",
]

# Windows GUI (pywebview winforms backend) needs pythonnet's managed assembly
# Python.Runtime.dll + clr_loader runtime config. PyInstaller doesn't grab these
# by default → "Failed to resolve Python.Runtime.Loader.Initialize" at launch.
# Collect them on Windows builds only (pythonnet isn't installed on macOS).
binaries = []
if sys.platform.startswith("win"):
    for _pkg in ("pythonnet", "clr_loader"):
        try:
            _d, _b, _h = collect_all(_pkg)
            datas += _d
            binaries += _b
            hiddenimports += _h
        except Exception as _e:
            print(f"[spec] collect_all({_pkg}) skipped: {_e}")
    hiddenimports += ["clr"]

# Heavy / removed-feature libs we deliberately keep OUT of the bundle.
excludes = [
    "google", "google.generativeai", "grpc", "stripe",
    "tkinter", "matplotlib", "PIL", "numpy", "pandas",
]

block_cipher = None

a = Analysis(
    ["launcher.py"],
    pathex=[BACKEND, ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="getifyco-listing-portal",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,            # GUI app — no terminal window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON_ICO,            # Windows .exe icon
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="getifyco-listing-portal",
)

# macOS .app bundle
app = BUNDLE(
    coll,
    name="getifyco-listing-portal.app",
    icon=ICON_ICNS,
    bundle_identifier="online.nguyenphamdieuhien.getifyco-listing-portal",
    info_plist={
        "CFBundleName": "GetifyCo Listing Portal",
        "CFBundleDisplayName": "GetifyCo Listing Portal",
        "NSHighResolutionCapable": True,
    },
)
