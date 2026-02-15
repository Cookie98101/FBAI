# -*- mode: python ; coding: utf-8 -*-
#
# Windows build for GitHub Actions (onedir).
# Bundles automation scripts into _internal/automation/scripts so the app can
# find and run/update tasks in frozen mode.

from __future__ import annotations

from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
)

# NOTE: PyInstaller executes .spec via exec() and may not provide __file__.
# SPECPATH is injected by PyInstaller and points to the directory containing this spec.
_spec_dir = globals().get("SPECPATH")
PROJECT_ROOT = Path(_spec_dir).resolve() if _spec_dir else Path.cwd().resolve()
APP_ROOT = PROJECT_ROOT / "fbai"

hiddenimports = []

# PyQtWebEngine needs extra collection on Windows.
hiddenimports += collect_submodules("PyQt5.QtWebEngineWidgets")
hiddenimports += collect_submodules("PyQt5.QtWebEngineCore")

datas = []
binaries = []

datas += collect_data_files("PyQt5.QtWebEngineWidgets", include_py_files=True)
datas += collect_data_files("PyQt5.QtWebEngineCore", include_py_files=True)
binaries += collect_dynamic_libs("PyQt5.QtWebEngineWidgets")
binaries += collect_dynamic_libs("PyQt5.QtWebEngineCore")

# App runtime resources/config.
def add_tree(src: Path, dest: str):
    if src.exists():
        datas.append((str(src), dest))

add_tree(APP_ROOT / "automation" / "scripts", "_internal/automation/scripts")
add_tree(APP_ROOT / "static", "static")
add_tree(APP_ROOT / "data", "data")

for cfg in [
    "automation_config.json",
    "remote_config.json",
    "simulator_config.json",
    "ui_config.json",
    "video_config.json",
]:
    p = APP_ROOT / cfg
    if p.exists():
        datas.append((str(p), "."))

a = Analysis(
    # facebook_dashboard.py intentionally does not call main() when frozen;
    # launcher.py is the correct frozen entrypoint (sets QtWebEngine env + calls main()).
    ["fbai/launcher.py"],
    pathex=[str(APP_ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="FBAI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
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
    name="FBAI",
)
