from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import settings
from app.database import init_db

from app.api import projects, materials, logs, configs, manuals, risks, topology, rules, reports


STATIC_DIR = settings.BASE_DIR / "static"
INDEX_HTML = STATIC_DIR / "index.html"


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if response.status_code == 404 and INDEX_HTML.exists():
            return await super().get_response("index.html", scope)
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    import sys
    import traceback
    try:
        await init_db()
    except Exception as e:
        # 把完整的异常栈打到 stderr，避免被 FastAPI 包装后截断
        print("[workbench] lifespan init_db FAILED:", file=sys.stderr, flush=True)
        traceback.print_exc(file=sys.stderr)
        raise
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_prefix = "/api/v1"

app.include_router(projects.router, prefix=api_prefix, tags=["Projects"])
app.include_router(materials.router, prefix=api_prefix, tags=["Materials"])
app.include_router(logs.router, prefix=api_prefix, tags=["Logs"])
app.include_router(configs.router, prefix=api_prefix, tags=["Configs"])
app.include_router(manuals.router, prefix=api_prefix, tags=["Manuals"])
app.include_router(risks.router, prefix=api_prefix, tags=["Risks"])
app.include_router(topology.router, prefix=api_prefix, tags=["Topology"])
app.include_router(rules.router, prefix=api_prefix, tags=["Rules"])
app.include_router(reports.router, prefix=api_prefix, tags=["Reports"])


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": settings.APP_VERSION}


@app.get("/")
async def root():
    if INDEX_HTML.exists():
        return FileResponse(str(INDEX_HTML))
    return {
        "message": "Network Analysis Workbench API",
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "api_prefix": api_prefix,
        "note": "Run 'cd frontend && npm run build' to generate static frontend.",
    }


@app.websocket("/ws/parse-progress/{task_id}")
async def parse_progress_ws(websocket: WebSocket, task_id: str):
    await websocket.accept()
    try:
        await websocket.send_json({"task_id": task_id, "status": "connected"})
        while True:
            data = await websocket.receive_text()
            await websocket.send_json({"task_id": task_id, "echo": data})
    except WebSocketDisconnect:
        pass


app.mount("/data", StaticFiles(directory=str(settings.DATA_DIR)), name="data")
app.mount("/exports", StaticFiles(directory=str(settings.EXPORT_DIR)), name="exports")

# SPA 静态文件挂载：始终挂载，用 check_dir=False 避免目录不存在时初始化报错。
# StaticFiles 在请求时动态读取文件，所以后端先启动、后构建前端也无需重启——
# 前端构建完成后，/assets/* 立即可以访问。
# 旧实现用 `if STATIC_DIR.exists(): app.mount(...)`，后端先于前端构建启动时
# 会被跳过，之后即使构建了前端，/assets/* 也一直 404。
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/", SPAStaticFiles(directory=str(STATIC_DIR), html=True, check_dir=False), name="frontend")
