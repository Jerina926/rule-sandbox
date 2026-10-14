from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from knowledge import kb

router = APIRouter(prefix="/api")


class AnalyzeRequest(BaseModel):
    society_id: str
    content: str
    goal: str = "提高满意度"
    scope: str = "部分群体"
    strength: str = "中等"
    session_id: str | None = None
    allow_inference: bool = False
    data_source: str = ""


@router.get("/health")
async def health(request: Request):
    st = request.app.state
    servers = {}
    for name in st.manager.configured():
        tools = await st.manager.list_tools(name)
        servers[name] = {
            "connected": st.manager.is_connected(name),
            "tools": tools or [],
            "error": st.manager.status.get(name, {}).get("error", ""),
        }
    return {
        "status": "ok",
        "mode": getattr(st, "mode", "agent"),
        "version": "pro-1.0",
        "llm_mode": st.gateway.mode(),
        "sessions": len(st.store.list_sessions()),
        "servers": servers,
    }


@router.get("/societies")
async def societies():
    return {"societies": [
        {"id": s["id"], "name": s["name"], "ico": s["ico"], "app": s["app"],
         "groups": s["groups"], "data": s["data"],
         "categories": [{"name": c["name"], "desc": c["desc"]} for c in s["cats"]]}
        for s in kb.SOC
    ]}


@router.post("/analyze")
async def analyze(req: AnalyzeRequest, request: Request):
    st = request.app.state
    content = (req.content or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="发布内容不能为空")
    if not kb.society(req.society_id):
        raise HTTPException(status_code=400, detail="未知社会类型: %s" % req.society_id)

    if req.session_id:
        doc = st.store.get(req.session_id)
        if doc is None:
            doc = st.store.create()
    else:
        doc = st.store.create()

    payload = req.model_dump()
    payload["run_index"] = len(doc["runs"]) + 1
    result = await st.planner.analyze(payload)

    if result.get("status") in ("ok", "mismatch"):
        doc = st.store.add_run(doc["session_id"], {k: payload.get(k) for k in
                                                    ("society_id", "content", "goal", "scope", "strength",
                                                     "allow_inference")}, result)
        result["session_id"] = doc["session_id"]
        if result["status"] == "ok":
            result["analysis"]["session_id"] = doc["session_id"]
            result["analysis"]["run_index"] = payload["run_index"]
    return result


@router.get("/sessions")
async def sessions(request: Request):
    return {"sessions": request.app.state.store.list_sessions()}


@router.get("/sessions/{sid}")
async def session_detail(sid: str, request: Request):
    doc = request.app.state.store.get(sid)
    if doc is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return doc


@router.post("/mcp/reload")
async def mcp_reload(request: Request):
    st = request.app.state
    results = await st.manager.reload(st.cfg)
    return {"reloaded": results, "servers": st.manager.status}
