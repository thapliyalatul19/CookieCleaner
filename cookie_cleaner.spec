# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Cookie Cleaner.

Creates a standalone Windows executable with:
- No console window (GUI only)
- All PyQt6 dependencies bundled
- Crypto dependencies for cookie decryption

Build command:
    pyinstaller cookie_cleaner.spec --clean

Output:
    dist/CookieCleaner.exe
"""

import sys
from pathlib import Path

# Determine if we're building a one-file or one-folder distribution
ONE_FILE = True

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        # Include any assets if they exist
        # ('assets/icon.ico', 'assets'),
    ],
    hiddenimports=[
        # PyQt6 modules
        'PyQt6',
        'PyQt6.QtWidgets',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.sip',
        # Cryptography for cookie decryption
        'cryptography',
        'cryptography.hazmat.primitives.ciphers.aead',
        'cryptography.hazmat.backends',
        # Windows-specific
        'win32crypt',
        'win32api',
        'win32con',
        'win32file',
        'pywintypes',
        # Standard library modules that might be needed
        'sqlite3',
        'json',
        'logging',
        'pathlib',
        'configparser',
        'uuid',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unnecessary modules to reduce size
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL',
        'IPython',
        'jupyter',
        'notebook',
        # Test frameworks
        'pytest',
        'pytest_qt',
        '_pytest',
        # Development tools
        'black',
        'flake8',
        'mypy',
        'pylint',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher,
)

if ONE_FILE:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name='CookieCleaner',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,  # No console window (GUI only)
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        # icon='assets/icon.ico',  # Uncomment if icon exists
    )
else:
    # One-folder distribution (useful for debugging)
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name='CookieCleaner',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        # icon='assets/icon.ico',
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name='CookieCleaner',
    )
