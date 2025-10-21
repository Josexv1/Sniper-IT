# -*- mode: python ; coding: utf-8 -*-
"""
Sniper-IT Agent V2 - PyInstaller Specification File
Cross-platform single-file executable builder for Windows and Linux
Usage: pyinstaller --clean --noconfirm Sniper-IT-Agent.spec
"""

import platform
import os
from pathlib import Path

# ============================================================================
# BUILD CONFIGURATION
# ============================================================================

# Determine current OS
current_os = platform.system()
is_windows = current_os == 'Windows'
is_linux = current_os == 'Linux'
is_macos = current_os == 'Darwin'

# Application metadata
APP_NAME = 'Sniper-IT-Agent'
APP_VERSION = '2.0.0'

# ============================================================================
# DATA FILES COLLECTION
# ============================================================================

datas = []

# Include all Python package directories
package_dirs = ['core', 'collectors', 'managers', 'cli', 'utils']
for pkg_dir in package_dirs:
    if os.path.exists(pkg_dir):
        datas.append((pkg_dir, pkg_dir))

# Include build metadata if it exists
if os.path.exists('core/build_info.json'):
    datas.append(('core/build_info.json', 'core'))

# Note: Config file is NOT bundled - users generate it via --setup command
# The executable will create config.yaml in the current working directory

# ============================================================================
# OS-SPECIFIC CONFIGURATION
# ============================================================================

if is_windows:
    exe_name = f'{APP_NAME}.exe'
    icon_file = 'assets/icon.ico' if os.path.exists('assets/icon.ico') else None
    console_mode = True
elif is_linux:
    exe_name = APP_NAME
    icon_file = None
    console_mode = True
elif is_macos:
    exe_name = APP_NAME
    icon_file = 'assets/icon.icns' if os.path.exists('assets/icon.icns') else None
    console_mode = True
else:
    exe_name = APP_NAME
    icon_file = None
    console_mode = True

# ============================================================================
# HIDDEN IMPORTS
# ============================================================================

# Core Python modules (IMPORTANT: email module is required by urllib3)
hidden_imports = [
    'argparse',
    'json',
    'platform',
    'subprocess',
    'datetime',
    'pathlib',
    'configparser',
    'hashlib',
    'email',
    'email.message',
    'email.parser',
]

# Third-party dependencies
hidden_imports.extend([
    'requests',
    'urllib3',
    'urllib3.exceptions',
    'urllib3.util',
    'urllib3.util.retry',
    'yaml',
    'rich',
    'rich.console',
    'rich.table',
    'rich.progress',
    'rich.panel',
    'rich.syntax',
    'rich.logging',
    'rich.traceback',
])

# Application-specific imports
hidden_imports.extend([
    'core',
    'core.api_client',
    'core.config_manager',
    'core.constants',
    'collectors',
    'collectors.system_collector',
    'collectors.monitor_collector',
    'managers',
    'managers.asset_manager',
    'managers.monitor_manager',
    'managers.setup_manager',
    'managers.sync_manager',
    'cli',
    'cli.formatters',
    'utils',
    'utils.exceptions',
])

# ============================================================================
# BINARIES AND EXCLUDES
# ============================================================================

binaries = []

# Modules to exclude (reduce size) - REMOVED 'email' from this list!
excludes = [
    'tkinter',
    'test',
    'unittest',
    'pydoc',
    'doctest',
    'xml.dom',
    'xml.sax',
    'xmlrpc',
    'sqlite3',
    'http.server',
    'distutils',
    'setuptools',
    'pip',
    'wheel',
]

# ============================================================================
# ANALYSIS
# ============================================================================

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=2,  # Optimize bytecode
)

# ============================================================================
# PYZ ARCHIVE
# ============================================================================

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=None  # No encryption for open source
)

# ============================================================================
# EXECUTABLE CONFIGURATION
# ============================================================================

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
    upx=True,  # Enable UPX compression
    upx_exclude=[],
    runtime_tmpdir=None,
    console=console_mode,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_file,
    # Single file configuration
    onefile=True,
)

# ============================================================================
# macOS APP BUNDLE (Optional)
# ============================================================================

if is_macos:
    app = BUNDLE(
        exe,
        name=f'{APP_NAME}.app',
        icon=icon_file,
        bundle_identifier=f'com.sniperit.agent.{APP_VERSION}',
        info_plist={
            'NSPrincipalClass': 'NSApplication',
            'NSHighResolutionCapable': 'True',
            'CFBundleShortVersionString': APP_VERSION,
        },
    )

# ============================================================================
# BUILD INFO
# ============================================================================

print(f"""
{'=' * 70}
Sniper-IT Agent V2 Build Configuration
{'=' * 70}
Platform: {current_os}
Executable: {exe_name}
Icon: {icon_file or 'None'}
Console Mode: {console_mode}
UPX Compression: Enabled
Optimization Level: 2
Data Files: {len(datas)} items
Hidden Imports: {len(hidden_imports)} modules
{'=' * 70}
""")
