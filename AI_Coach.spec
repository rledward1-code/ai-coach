# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import copy_metadata

datas = [('app.py', '.'), ('coach_engine.py', '.'), ('prompts.py', '.'), ('data_processor.py', '.'), ('history_manager.py', '.'), ('memory_manager.py', '.'), ('strava_manager.py', '.'), ('assets', 'assets'), ('.streamlit', '.streamlit')]
datas += copy_metadata('streamlit')
datas += copy_metadata('plotly')
datas += copy_metadata('google-generativeai')
datas += copy_metadata('openai')
datas += copy_metadata('fitparse')
datas += copy_metadata('pandas')
datas += copy_metadata('numpy')
datas += copy_metadata('requests')


a = Analysis(
    ['run_main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=['plotly', 'plotly.graph_objects', 'plotly.express'],
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
    [],
    exclude_binaries=True,
    name='AI_Coach',
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
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AI_Coach',
)
