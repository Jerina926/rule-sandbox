from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from knowledge import kb
from backend.agents.explainable_models import run_all as em_run_all
from backend.agents.explainable_models import list_models as em_list_models
from backend.agents.school_simulation import (
    list_personas, get_personas_for_content,
    list_scales, get_demographics,
    list_calibration_fields, compute_calibrated_proportions, compare_with_default,
    run_fusion, network_for_content, list_chain_templates,
)
from backend.db.store import CasesRepo, SourcesRepo

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
    data_source_url: str = ""


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


@router.get("/attribute-test")
async def attribute_test():
    """控制变量测试：固定社会类型/发布内容/群体人数/数据来源，只改变一个规则属性比较前后结果。"""
    from knowledge import engine
    return engine.attribute_contrast_test()


class ExplainRequest(BaseModel):
    society_id: str
    category_name: str = ""
    content: str = ""
    scope: str = "部分群体"
    strength: str = "中等"


@router.get("/models/catalog")
async def models_catalog():
    """挑战杯答辩用：返回 5 个可解释模型的元数据（中文标题、用途、产出阶段、公式索引）。"""
    return {"models": em_list_models()}


@router.post("/explain")
async def explain(req: ExplainRequest):
    """独立端点：直接调用 5 个可解释模型，返回每个模型的 result + computation_basis + factor_breakdown + formula + evidence_refs + confidence。"""
    cat = req.category_name
    if not cat:
        # 自动跑一遍 scene_detection 推断
        from backend.agents.explainable_models import scene_detection
        sd = scene_detection.run(req.society_id, req.content)
        if sd.get("result", {}).get("status") != "error" and sd.get("result", {}).get("category_name"):
            cat = sd["result"]["category_name"]
        else:
            return {"status": "error", "message": "未能识别规则类别，请提供 category_name 或检查 content 关键词"}
    out = em_run_all(req.society_id, cat, req.content, req.scope, req.strength)
    return {"status": "ok", "society_id": req.society_id, "category_name": cat,
            "scope": req.scope, "strength": req.strength, "explanation": out}


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
# 嵌入 5 个可解释模型（用于挑战杯答辩展示；前后端零侵入）
        try:
            cat_name = result["analysis"]["identification"]["category"]["name"]
            explanation = em_run_all(
                req.society_id, cat_name, content,
                payload.get("scope", "部分群体"), payload.get("strength", "中等"))
            result["analysis"]["explanation"] = explanation
        except Exception as e:
            result["analysis"]["explanation"] = {"_error": str(e)}

        # 嵌入虚拟学校仿真：人物画像 + 人口结构 + 本校校准 + 双源融合
        try:
            metrics_raw = result["analysis"].get("metrics", {})
            # 将可能为字符串的字段转为数值（strength/diff/hole 等是『低/中/高』字符串）
            def _to_num(v, default=50):
                if v is None:
                    return default
                if isinstance(v, (int, float)):
                    return float(v)
                s = str(v).strip()
                mapping = {"低": 25, "较低": 30, "中": 50, "中等": 50, "较高": 65, "高": 75, "较高": 70}
                if s in mapping:
                    return float(mapping[s])
                try:
                    return float(s)
                except Exception:
                    return default
            metrics = {
                "approve": _to_num(metrics_raw.get("approve"), 50),
                "oppose":  _to_num(metrics_raw.get("oppose"), 30),
                "risk":    _to_num(metrics_raw.get("risk"), 35),
                "diff":    _to_num(metrics_raw.get("diff"), 40),
                "fair":    _to_num(metrics_raw.get("fairness", metrics_raw.get("fair")), 70),
                "vuln":    _to_num(metrics_raw.get("vuln", metrics_raw.get("hole")), 30),
            }
            cat_name = result["analysis"]["identification"]["category"]["name"]
            fusion = run_fusion(
                scale="普通本科高校",
                calibration={},
                metrics=metrics,
                questionnaire_data=None,
                weights=None,
                content=content,
                category_hint=cat_name,
            )
            personas_rel = get_personas_for_content(
                content,
                result["analysis"]["identification"]["category"]["name"]
            )
            result["analysis"]["school_simulation"] = {
                "personas_relevance": {
                    "strong": personas_rel["strong"][:8],    # 强相关前 8
                    "weak_count": personas_rel["counts"]["weak"],
                    "dormant_count": personas_rel["counts"]["dormant"],
                    "category_totals": personas_rel["category_totals"],
                },
                "demographics": {
                    "scale": fusion["scale"],
                    "cohort": fusion["cohort"],
                },
                "calibration": {
                    "credibility": fusion["calibration"]["credibility"],
                    "filled_count": fusion["calibration"]["filled_count"],
                    "total_numeric_fields": fusion["calibration"]["total_numeric_fields"],
                    "warnings": fusion["calibration"]["warnings"][:6],
                    "source_breakdown": fusion["calibration"]["source_breakdown"],
                },
                "dual_source_fusion": {
                    "weights": fusion["weights"],
                    "persona_side": {k: v for k, v in fusion["persona_side"].items() if k != "breakdown"},
                    "questionnaire_side": fusion["questionnaire_side"],
                    "fused": fusion["fused"],
                    "weight_explanation": fusion["fused"]["weight_explanation"],
                    "recommended_plan": fusion["recommended_plan"],
                },
                # V4.0 新增：虚拟人物反应摘要 + 双源融合依据 + 人物关系网络
                "reaction_summary": fusion.get("reaction_summary", {}),
                "fusion_basis": fusion.get("fusion_basis", {}),
                "persona_network": fusion.get("persona_network", {}),
            }
        except Exception as e:
            result["analysis"]["school_simulation"] = {"_error": str(e)}

        # 持久化到 SQLite（cases + questionnaires + answers + public_sources + simulation_reports）
        try:
            persist_result = CasesRepo.persist(result["analysis"], request=payload)
            if persist_result.get("ok"):
                result["analysis"]["_db_case_id"] = persist_result["case_id"]
                result["analysis"]["_db"] = {
                    "case_id": persist_result["case_id"],
                    "sections": persist_result["sections"],
                    "items": persist_result["items"],
                    "db_path": persist_result["db_path"],
                }
        except Exception as e:
            result["analysis"]["_db_error"] = str(e)
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


# ============================================================
# SQLite 持久化层相关路由（cases / public_sources）
# ============================================================

class UpsertAnswersRequest(BaseModel):
    case_id: str
    answers: list  # [{section, question, selected}, ...]


class AddSourceRequest(BaseModel):
    society_id: str = ""
    name: str
    url: str = ""
    category: str = "general"
    use_field: str = ""


@router.get("/cases")
async def list_cases(society_id: str = "", limit: int = 50, offset: int = 0,
                     days: int = None, status: str = ""):
    """列出历史案例。可按社会 / 状态 / 时间窗筛选。"""
    return {"cases": CasesRepo.list_cases(society_id=society_id, limit=limit,
                                          offset=offset, days=days, status=status)}


@router.get("/cases/stats")
async def cases_stats(days: int = 30):
    """统计：总数、状态分布、社会分布、推荐方案分布（用于挑战杯现场 dashboard）。"""
    return CasesRepo.stats(days=days)


@router.get("/cases/compare")
async def compare_cases(ids: str):
    """多 case 并列对比。ids 用英文逗号分隔，例如 ?ids=a,b,c。"""
    case_ids = [x for x in ids.split(",") if x]
    if not case_ids:
        return {"cases": []}
    return {"cases": CasesRepo.compare_cases(case_ids)}


@router.get("/cases/{case_id}")
async def get_case_detail(case_id: str):
    """单 case 完整详情（含问卷、答案、报告、5 模型 explanation）。"""
    data = CasesRepo.get_case(case_id)
    if data is None:
        raise HTTPException(status_code=404, detail="case_id 不存在")
    return data


@router.delete("/cases/{case_id}")
async def delete_case(case_id: str):
    return CasesRepo.delete_case(case_id)


@router.post("/cases/{case_id}/answers")
async def upsert_answers(case_id: str, req: UpsertAnswersRequest):
    """用户在答完问卷后调此接口，selected 写回 answers 表。"""
    if req.case_id != case_id:
        raise HTTPException(status_code=400, detail="case_id 不匹配")
    return CasesRepo.upsert_answers(case_id, req.answers)


@router.get("/sources")
async def list_sources(society_id: str = "", category: str = ""):
    """列出已注册的公开数据源（按社会/类别筛选）。"""
    return {"sources": SourcesRepo.list_sources(society_id=society_id, category=category)}


@router.post("/sources")
async def add_source(req: AddSourceRequest):
    return SourcesRepo.add_source(req.society_id, req.name, req.url,
                                  req.category, req.use_field)


@router.get("/db/info")
async def db_info(request: Request):
    """数据库元信息（路径、表数量、各表记录数、文件大小）。"""
    import os
    from backend.db import get_conn
    db_path = getattr(request.app.state, "db_path", None) or ""
    info = {"db_path": db_path, "exists": os.path.exists(db_path) if db_path else False}
    if info["exists"]:
        info["size_bytes"] = os.path.getsize(db_path)
        try:
            conn = get_conn()
            cur = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
                "ORDER BY name")
            tables = [r["name"] for r in cur.fetchall()]
            info["tables"] = tables
            counts = {}
            for t in tables:
                try:
                    c = conn.execute(f"SELECT COUNT(*) c FROM {t}").fetchone()["c"]
                    counts[t] = c
                except Exception:
                    counts[t] = -1
            info["counts"] = counts
        except Exception as e:
            info["error"] = str(e)
    return info


# ============================================================
# 虚拟学校仿真：人物画像 / 人口结构 / 本校校准 / 双源融合
# ============================================================

@router.get("/personas")
async def get_personas(society_id: str = "school", content: str = "",
                       category_name: str = ""):
    """
    虚拟学校人物画像库：根据 society_id 返回全部人物；若有 content/category_name，
    进一步划分 strong / weak / dormant 三档。
    """
    items = list_personas()
    cat_hint = ""
    if not category_name and content:
        # 自动尝试用 scene_detection 推断 category_hint
        from backend.agents.explainable_models import scene_detection
        sd = scene_detection.run(society_id, content)
        cat_hint = sd.get("result", {}).get("category_name", "") or ""
    if not category_name:
        category_name = cat_hint

    relevance = get_personas_for_content(content or "", category_name)

    # 整库按类别汇总
    category_totals = {}
    for p in items:
        cat = p["category"]
        category_totals[cat] = category_totals.get(cat, 0) + 1

    return {
        "society_id": society_id,
        "category_name": category_name,
        "total": len(items),
        "category_totals": category_totals,
        "relevance": relevance,
        "disclaimer": "所有人物均为虚拟角色原型，仅用于模拟推演，不代表任何真实个体。",
    }


@router.get("/demographics")
async def get_demographics_api(scale: str = "普通本科高校", overrides: str = ""):
    """
    人口结构比例与权重模型：返回 5 大类 × 各 archetype 的比例/权重/影响力。
    overrides: 可选 JSON 字符串，例如 {"普通住校生": 0.5}。
    """
    overrides_dict = {}
    if overrides:
        import json as _json
        try:
            overrides_dict = _json.loads(overrides)
        except Exception:
            overrides_dict = {}
    demo = get_demographics(scale, overrides_dict)
    return {
        "scale": scale,
        "description": next((d["description"] for d in list_scales() if d["scale"] == scale), ""),
        "demographics": demo,
        "total_archetypes": len(demo),
        "disclaimer": "比例仅用于模拟推演，不代表真实学校数据；用户可手动调整。",
    }


@router.get("/scales")
async def get_scales():
    """列出 5 种学校规模及其描述。"""
    return {"scales": list_scales()}


@router.get("/calibration/fields")
async def calibration_fields():
    """本校校准字段定义（20+ 字段）。"""
    return {"fields": list_calibration_fields()}


class CalibrationRequest(BaseModel):
    scale: str = "普通本科高校"
    calibration: dict = {}


@router.post("/calibration")
async def post_calibration(req: CalibrationRequest):
    """根据本校数据计算校准后比例 / 字段状态 / 数据可信度 / 数据来源。"""
    return compute_calibrated_proportions(req.scale, req.calibration)


@router.post("/calibration/compare")
async def post_calibration_compare(req: CalibrationRequest):
    """校准前后对比：哪些 archetype 占比上升 / 下降。"""
    return compare_with_default(req.scale, req.calibration)


class FusionRequest(BaseModel):
    scale: str = "普通本科高校"
    calibration: dict = {}
    questionnaire_data: dict | None = None
    weights: dict | None = None
    metrics: dict = {}
    content: str = ""
    category_hint: str = ""


@router.post("/fusion")
async def post_fusion(req: FusionRequest):
    """
    双源融合：人口比例 → 校准 → 虚拟人物侧 → 问卷侧 → 双源融合 → 群体差异。
    """
    metrics = req.metrics or {
        "approve": 50, "oppose": 30, "risk": 35, "diff": 40, "fair": 70, "vuln": 30,
    }
    return run_fusion(
        req.scale, req.calibration, metrics,
        questionnaire_data=req.questionnaire_data,
        weights=req.weights,
        content=req.content,
        category_hint=req.category_hint,
    )


# ============================================================
# V4.0 新增：人物关系网络
# ============================================================

@router.get("/relations")
async def get_relations(content: str = "", category_hint: str = ""):
    """
    虚拟校园人物关系网络：根据发布内容，返回命中的节点/边/链条。
    可视化用，挑战杯演示场景必备。
    """
    return network_for_content(content, category_hint)


@router.get("/relations/templates")
async def get_relation_templates():
    """列出全部关系链条模板（不绑定具体发布内容）。"""
    return {"templates": list_chain_templates()}
