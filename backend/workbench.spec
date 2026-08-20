# PyInstaller spec for Network Analysis Workbench
# 用法: pyinstaller workbench.spec

import sys
from pathlib import Path

block_cipher = None
base = Path(SPECPATH).resolve()  # backend/ 目录

# 数据文件：(源路径, 目标路径)
datas = [
    # 前端静态资源
    (str(base / "static"), "static"),
    # 规则文件
    (str(base / "app" / "rules"), "app/rules"),
    # 报告模板
    (str(base / "app" / "data" / "templates"), "app/data/templates"),
]

# 隐式导入（PyInstaller 无法自动检测的依赖）
hiddenimports = [
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "aiosqlite",
    "sqlalchemy.dialects.sqlite",
    "sqlalchemy.dialects.sqlite.aiosqlite",
    "pydantic",
    "pydantic_core",
    "pydantic_settings",
    "pdfplumber",
    "pdfminer",
    "lxml._elementpath",
    "PIL._tkinter_finder",
]

a = Analysis(
    ["run_standalone.py"],
    pathex=[str(base)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "pytest", "IPython"],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="network-workbench",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # 保留控制台窗口，方便查看日志
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
