"""PyInstaller 单文件打包入口。

启动逻辑：
1. 解析静态资源/规则/模板路径（来自 _MEIPASS 临时解压目录）
2. 数据目录（DB/上传/导出）放在 exe 同级目录，持久化
3. 启动 uvicorn 后台服务
4. 自动打开默认浏览器
"""
import os
import sys
import threading
import time
import webbrowser
from pathlib import Path


def _resolve_base_dir() -> Path:
    """打包模式下，资源在 _MEIPASS；开发模式下在 backend/ 目录。"""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent


def _resolve_data_dir() -> Path:
    """数据目录放在 exe 同级（打包模式）或 backend/data（开发模式）。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "data"
    return Path(__file__).resolve().parent / "data"


def main():
    base_dir = _resolve_base_dir()
    data_dir = _resolve_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)

    # 注入路径到环境变量，供 config.py 使用
    os.environ["WORKBENCH_BASE_DIR"] = str(base_dir)
    os.environ["WORKBENCH_DATA_DIR"] = str(data_dir)

    # 确保模块可导入（打包模式下 app 包在 _MEIPASS/app）
    if str(base_dir) not in sys.path:
        sys.path.insert(0, str(base_dir))

    port = int(os.environ.get("WORKBENCH_PORT", "8000"))
    host = os.environ.get("WORKBENCH_HOST", "127.0.0.1")
    url = f"http://{host}:{port}"

    # 后台打开浏览器
    def _open_browser():
        time.sleep(2)
        webbrowser.open(url)

    threading.Thread(target=_open_browser, daemon=True).start()

    # 直接导入 app 对象（避免字符串导入在打包模式下失败）
    from app.main import app
    import uvicorn
    print(f"网络环境分析工作台启动中...")
    print(f"访问地址: {url}")
    print(f"数据目录: {data_dir}")
    print(f"按 Ctrl+C 退出")
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()
