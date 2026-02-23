# -*- mode: python ; coding: utf-8 -*-

import os
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = collect_submodules("webview")
ROOT_DIR = os.path.abspath(os.getcwd())
ICON_PATH = os.path.join(ROOT_DIR, 'source', 'app-desktop', 'ddr.ico')

a = Analysis(
    [os.path.join(ROOT_DIR, 'source', 'app-desktop', 'ddr-desktop.py')],
    pathex=[],
    binaries=[],
    datas=[
        (os.path.join(ROOT_DIR, 'source', 'app-desktop', 'ddr-engine.py'), '.'),
        (os.path.join(ROOT_DIR, 'source', 'app-web', 'ddr.html'), 'app-web'),
        (os.path.join(ROOT_DIR, 'source', 'app-web', 'ddr.png'), 'app-web'),
    ],
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
    name='ddr',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    icon=ICON_PATH if os.path.exists(ICON_PATH) else None,
    console=True,
    uac_admin=False,
    uac_uiaccess=False,
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
    upx=True,
    upx_exclude=[],
    name='ddr-portable',
)
