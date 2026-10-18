import asyncio
import os
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import yaml
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.agents.planner import Planner
from backend.agents.session_store import SessionStore
from backend.api import routes
from backend.core.llm_gateway import LLMGateway
from backend.core.mcp_manager import MCPManager
from backend.core.validator import Validator
from backend.db import init_schema as db_init_schema, resolve_db_path, backup as db_backup

CONFIG_PATH = os.path.join(ROOT, "config.yaml")

DEFAULT_CORS_ORIGINS = [
    "https://9aa6eec419d14da9a75443262bfbc669.app.workbuddy.host",
    "http://localhost:8017",
    "http://127.0.0.1:8017",
    "http://localhost:3000",
    "null",
]


def load_config(path=CONFIG_PATH):
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if os.environ.get("RSB_MCP_ENABLED", "1") == "0":
        cfg.setdefault("mcp", {})["servers"] = {}
    for name, entry in cfg.get("mcp", {}).get("servers", {}).items():
        entry["args"] = [os.path.join(ROOT, a) if not os.path.isabs(a) else a for a in entry.get("args", [])]
    return cfg


def cors_origins(cfg):
    origins = list(DEFAULT_CORS_ORIGINS)
    origins += (cfg.get("cors", {}) or {}).get("origins", [])
    env_origins = os.environ.get("RSB_CORS_ORIGINS", "")
    origins += [o.strip() for o in env_origins.split(",") if o.strip()]
    seen, out = set(), []
    for o in origins:
        if o and o not in seen:
            seen.add(o)
            out.append(o)
    return out


async def _backup_loop(sessions_dir, status):
    """每 RSB_BACKUP_INTERVAL 秒（默认 1800）把 SQLite 与会话 JSON 备份到 GitHub；未配置 token 时空转。"""
    while True:
        await asyncio.sleep(int(os.environ.get("RSB_BACKUP_INTERVAL", "1800")))
        if not db_backup.enabled():
            status["enabled"] = False
            continue
        status["enabled"] = True
        fails = []
        try:
            if not await asyncio.to_thread(db_backup.backup, resolve_db_path()):
                fails.append("db")
        except Exception as e:
            fails.append("db: %s" % e)
            print("DB backup warning:", e)
        try:
            if not await asyncio.to_thread(db_backup.backup_sessions, sessions_dir):
                fails.append("sessions")
        except Exception as e:
            fails.append("sessions: %s" % e)
            print("Sessions backup warning:", e)
        if fails:
            status["consecutive_failures"] += 1
            status["last_error"] = ", ".join(fails)
        else:
            status["last_success"] = datetime.now().isoformat(timespec="seconds")
            status["consecutive_failures"] = 0
            status["last_error"] = None


def create_app(cfg=None):
    cfg = cfg or load_config()
    app = FastAPI(title="规则沙盒：虚拟社会反应预演系统", version="pro-1.0")
    app.state.cfg = cfg
    app.state.mode = os.environ.get("RSB_MODE", cfg.get("server", {}).get("mode", "agent"))
    app.state.backup_status = {"enabled": False, "last_success": None, "last_error": None, "consecutive_failures": 0}
    app.state.analyze_throttle = {}
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins(cfg),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    # 写操作鉴权：POST/PUT/DELETE 请求的 /api/* 必须携带与 RSB_API_KEY 一致的 X-API-Key，
    # 用于挡住爬虫与误操作；未配置 RSB_API_KEY 时跳过校验（保持零配置可运行）。
    @app.middleware("http")
    async def api_key_guard(request, call_next):
        expected = os.environ.get("RSB_API_KEY", "").strip()
        if (expected and request.method in ("POST", "PUT", "PATCH", "DELETE")
                and request.url.path.startswith("/api/")):
            provided = request.headers.get("X-API-Key", "").strip()
            if not provided or provided != expected:
                return JSONResponse(status_code=401, content={"detail": "无效或缺失的 X-API-Key"})
        return await call_next(request)

    print("Write-op API key guard:",
          "enabled" if os.environ.get("RSB_API_KEY", "").strip() else "disabled (RSB_API_KEY not set)",
          flush=True)

    app.state.manager = MCPManager(cfg)
    app.state.gateway = LLMGateway(cfg.get("llm", {}))
    app.state.validator = Validator()
    app.state.planner = Planner(app.state.manager, app.state.gateway, app.state.validator)
    session_dir = os.path.join(ROOT, cfg.get("session", {}).get("dir", "backend/data/sessions"))
    app.state.store = SessionStore(session_dir)
    app.state.sessions_dir = session_dir
    app.include_router(routes.router)

    @app.on_event("startup")
    async def _startup():
        try:
            await app.state.manager.connect_all()
        except Exception as e:
            print("MCP startup warning:", e)
        try:
            raw_path = resolve_db_path()
            await asyncio.to_thread(db_backup.restore, raw_path)
        except Exception as e:
            print("DB restore warning:", e)
        try:
            await asyncio.to_thread(db_backup.restore_sessions, app.state.sessions_dir)
        except Exception as e:
            print("Sessions restore warning:", e)
        try:
            db_path = db_init_schema()
            print("DB initialized:", db_path)
            app.state.db_path = db_path
        except Exception as e:
            print("DB init warning:", e)
            app.state.db_path = None
        app.state.backup_status["enabled"] = db_backup.enabled()
        asyncio.create_task(_backup_loop(app.state.sessions_dir, app.state.backup_status))

    @app.on_event("shutdown")
    async def _shutdown():
        await app.state.manager.close_all()

    static_dir = os.path.join(ROOT, "frontend")
    if os.path.isdir(static_dir):
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="frontend")
    return app


app = create_app()

if __name__ == "__main__":
    cfg = load_config()
    server = cfg.get("server", {})
    uvicorn.run("backend.main:app", host=server.get("host", "127.0.0.1"),
                port=int(server.get("port", 8017)), reload=False)
