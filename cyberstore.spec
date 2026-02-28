# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for CyberStore - bundles textual CSS and all dependencies

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = []
# Bundle textual's built-in CSS themes and assets
datas += collect_data_files("textual")
# Bundle rich data files (includes _unicode_data compiled modules)
datas += collect_data_files("rich")
# Bundle our custom TCSS stylesheets (cyberstore/styles/*.tcss)
# Destination path mirrors the source so Path(__file__).parent resolves correctly
datas += [("cyberstore/styles", "cyberstore/styles")]

hiddenimports = []
hiddenimports += collect_submodules("textual")
hiddenimports += collect_submodules("rich")
hiddenimports += collect_submodules("boto3")
hiddenimports += collect_submodules("botocore")
hiddenimports += [
    "pyperclip",
    "humanize",
    "tomli_w",
]

a = Analysis(
    ["cyberstore/__main__.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Exclude heavy stdlib modules not needed at runtime
    excludes=["tkinter", "test", "unittest", "pydoc"],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="cyberstore",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,  # macOS: disable argv emulation for CLI apps
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
