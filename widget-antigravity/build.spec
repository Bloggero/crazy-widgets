# -*- mode: python ; coding: utf-8 -*-
import sys
import os

block_cipher = None

BASE_DIR = os.path.abspath(SPECPATH)
RESOURCES_DIR = os.path.join(BASE_DIR, 'src', 'resources')

added_files = [
    (RESOURCES_DIR, 'resources'),
    (RESOURCES_DIR, 'src/resources'),
]

a = Analysis(
    ['src/main.py'],
    pathex=[BASE_DIR],
    binaries=[],
    datas=added_files,
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtNetwork',
        'psutil',
        'requests',
        'dateutil',
        'dateutil.parser',
        'sqlite3',
        'logging',
        'logging.handlers',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'scipy', 'pandas', 'IPython'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='AntigravityQuotaMonitor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(RESOURCES_DIR, 'icon.ico'),
)
