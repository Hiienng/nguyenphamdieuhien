# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Getify desktop app (macOS .app + Windows .exe)."""
import os
from PyInstaller.utils.hooks import collect_submodules

SPEC_DIR = os.path.abspath(SPECPATH)          # desktop/
ROOT = os.path.dirname(SPEC_DIR)              # project dir (nguyenphamdieuhien)
BACKEND = os.path.join(ROOT, "backend")

# --- bundled data: static frontend, docs, extension asset, and .env ---------
datas = [
    (os.path.join(ROOT, "frontend"), "frontend"),
    (os.path.join(ROOT, "docs"), "docs"),
]
_ext = os.path.join(ROOT, "extension-keyword-main", "Archive.pxi")
if os.path.exists(_ext):
    datas.append((_ext, "extension-keyword-main"))
_env = os.path.join(ROOT, ".env")
if os.path.exists(_env):
    datas.append((_env, "."))

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

# Heavy / removed-feature libs we deliberately keep OUT of the bundle.
excludes = [
    "google", "google.generativeai", "grpc", "stripe",
    "tkinter", "matplotlib", "PIL", "numpy", "pandas",
]

block_cipher = None

a = Analysis(
    ["launcher.py"],
    pathex=[BACKEND, ROOT],
    binaries=[],
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
    icon=None,
    bundle_identifier="online.nguyenphamdieuhien.getifyco-listing-portal",
    info_plist={
        "CFBundleName": "GetifyCo Listing Portal",
        "CFBundleDisplayName": "GetifyCo Listing Portal",
        "NSHighResolutionCapable": True,
    },
)
