import asyncio
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import yaml
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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


async def _backup_loop():
    """每 RSB_BACKUP_INTERVAL 秒（默认 1800）把 SQLite 备份到 GitHub；未配置 token 时空转。"""
    while True:
        await asyncio.sleep(int(os.environ.get("RSB_BACKUP_INTERVAL", "1800")))
        try:
            await asyncio.to_thread(db_backup.backup, resolve_db_path())
        except Exception as e:
            print("DB backup warning:", e)


def create_app(cfg=None):
    cfg = cfg or load_config()
    app = FastAPI(title="规则沙盒：虚拟社会反应预演系统", version="pro-1.0")
    app.state.cfg = cfg
    app.state.mode = os.environ.get("RSB_MODE", cfg.get("server", {}).get("mode", "agent"))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins(cfg),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    app.state.manager = MCPManager(cfg)
    app.state.gateway = LLMGateway(cfg.get("llm", {}))
    app.state.validator = Validator()
    app.state.planner = Planner(app.state.manager, app.state.gateway, app.state.validator)
    app.state.store = SessionStore(os.path.join(ROOT, cfg.get("session", {}).get("dir", "backend/data/sessions")))
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
            db_path = db_init_schema()
            print("DB initialized:", db_path)
            app.state.db_path = db_path
        except Exception as e:
            print("DB init warning:", e)
            app.state.db_path = None
        asyncio.create_task(_backup_loop())

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
