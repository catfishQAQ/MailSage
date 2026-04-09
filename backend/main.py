import logging
import os
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

from database import init_db
from routers import accounts, emails, ai, settings, send


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时：初始化数据库 + 启动 AI 队列 worker
    await init_db()

    from services.queue_service import ai_queue
    import asyncio
    worker_task = asyncio.create_task(ai_queue.start_worker())

    # 启动 APScheduler 定时任务（从 DB 读取用户配置的同步频率）
    from scheduler import start_scheduler, stop_scheduler
    await start_scheduler()

    yield

    # 关闭时：广播关闭哨兵（让所有 SSE 连接立即退出），再停止 worker 和 scheduler
    from services.queue_service import broadcast_shutdown
    broadcast_shutdown()
    worker_task.cancel()
    stop_scheduler()


app = FastAPI(
    title="MailSage",
    description="本地优先的多平台邮件聚合客户端 API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(accounts.router, prefix="/api/accounts", tags=["accounts"])
app.include_router(emails.router, prefix="/api/emails", tags=["emails"])
app.include_router(ai.router, prefix="/api/ai", tags=["ai"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(send.router, prefix="/api/emails", tags=["emails"])


@app.get("/api/health")
async def health():
    return {"status": "ok"}


def _frontend_dist_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "frontend" / "dist"


def _serve_static_frontend() -> bool:
    return os.getenv("MAILSAGE_SERVE_FRONTEND", "").lower() in {"1", "true", "yes"}


if _serve_static_frontend():
    frontend_dist = _frontend_dist_dir()
    assets_dir = frontend_dist / "assets"

    if frontend_dist.exists() and (frontend_dist / "index.html").exists():
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")

        @app.get("/", include_in_schema=False)
        async def spa_root():
            return FileResponse(frontend_dist / "index.html")


        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_fallback(full_path: str):
            requested_path = (frontend_dist / full_path).resolve()
            if (
                full_path
                and requested_path.is_relative_to(frontend_dist)
                and requested_path.exists()
                and requested_path.is_file()
            ):
                return FileResponse(requested_path)
            return FileResponse(frontend_dist / "index.html")
