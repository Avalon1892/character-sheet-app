"""PyInstaller one-folder definition for the Character Sheet App."""

from pathlib import Path


# PyInstaller exposes SPECPATH as the directory containing this specification,
# not the specification filename itself.
project_root = Path(SPECPATH).resolve().parent

analysis = Analysis(
    [str(project_root / "main.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        (str(project_root / "data" / "pf1e"), "data/pf1e"),
        (str(project_root / "app" / "assets"), "app/assets"),
    ],
    hiddenimports=[
        # Sheet presentations are intentionally discovered through the modular
        # registry at runtime, so the freezer cannot infer these imports.
        "app.ui.character_sheet",
        "app.ui.original_spheres_sheet",
        "app.ui.ultra_sheet",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "unittest"],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(analysis.pure)

executable = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="Character Sheet App",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

bundle = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Character Sheet App",
)
