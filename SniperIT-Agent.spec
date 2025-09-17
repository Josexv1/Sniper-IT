# -*- mode: python ; coding: utf-8 -*-
# SniperIT Agent - Cross-platform PyInstaller spec for single file executables
# Automatically builds single file executables for Windows (.exe) and Linux
# Usage: pyinstaller --clean --noconfirm SniperIT-Agent.spec

import platform
import os

# Determine current OS
current_os = platform.system()

# Updated data files for new structure - include config files in root
datas = [
    ('config', 'config'),
    ('collectors', 'collectors'), 
    ('managers', 'managers'),
    ('utils', 'utils')
]

# Include actual config files if they exist
if os.path.exists('config/config.ini'):
    datas.append(('config/config.ini', '.'))
if os.path.exists('config/custom_fields.json'):
    datas.append(('config/custom_fields.json', '.'))
if os.path.exists('config.ini'):
    datas.append(('config.ini', '.'))
if os.path.exists('custom_fields.json'):
    datas.append(('custom_fields.json', '.'))

# OS-specific executable name
if current_os == 'Windows':
    exe_name = 'SniperIT-Agent.exe'
    icon_file = 'app_icon.ico' if os.path.exists('app_icon.ico') else None
else:
    exe_name = 'SniperIT-Agent'
    icon_file = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'requests', 
        'urllib3', 
        'argparse', 
        'json', 
        'base64', 
        'binascii', 
        'platform',
        'warnings',
        'configparser',
        'subprocess',
        'datetime'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data)

# Single file executable configuration
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=exe_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_file,
    # Single file configuration
    onefile=True,
    # Automatic confirmation (no prompts)
    noconfirm=True
)
