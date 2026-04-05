# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['run_main.py'],
    pathex=[],
    binaries=[],
    datas=[('app.py', '.'), ('coach_engine.py', '.'), ('prompts.py', '.'), ('data_processor.py', '.'), ('history_manager.py', '.'), ('memory_manager.py', '.'), ('strava_manager.py', '.'), ('assets', 'assets'), ('.streamlit', '.streamlit')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='AI Coach',
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
)
