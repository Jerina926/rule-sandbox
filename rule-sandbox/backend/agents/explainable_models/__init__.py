"""5 个可解释推演模型的统一出口。

提供：
  - run_all(society_id, category_name, content, scope, strength, metrics=None)
      返回 5 个模型的结果字典，结构为：
        {
          "scene_detection": {...},
          "cohort_profile": {...},
          "support_calculation": {...},
          "risk_chain": {...},
          "alternative_compare": {...},
          "_summary": {...}
        }
  - CATALOG 模型元数据（用于挑战杯答辩展示）
  - get_model(name) 按名取单个模型
"""
from . import scene_detection
from . import cohort_profile
from . import support_calculation
from . import risk_chain
from . import alternative_compare
from .base import CATALOG

MODELS = {
    "scene_detection": scene_detection,
    "cohort_profile": cohort_profile,
    "support_calculation": support_calculation,
    "risk_chain": risk_chain,
    "alternative_compare": alternative_compare,
}


def get_model(name):
    return MODELS.get(name)


def list_models():
    return CATALOG


def run_all(society_id="", category_name="", content="", scope="部分群体", strength="中等",
            goal="提高满意度", data_source=""):
    """顺序调用 5 个模型并汇总。失败时不影响其它模型继续返回。

    模型 3（支持度计算）直接调用主推演引擎 simulate_metrics，
    goal / data_source 与 /api/analyze 保持一致，保证两处结果逐字段一致。
    """
    metrics = support_calculation.run(scope, strength, goal=goal, data_source=data_source)
    risk_score = metrics.get("result", {}).get("risk", 42)

    out = {}
    for key, mod in MODELS.items():
        try:
            if key == "scene_detection":
                out[key] = mod.run(society_id, content)
            elif key == "cohort_profile":
                out[key] = mod.run(society_id, category_name)
            elif key == "support_calculation":
                out[key] = metrics
            elif key == "risk_chain":
                out[key] = mod.run(society_id, category_name, risk_score=risk_score)
            elif key == "alternative_compare":
                out[key] = mod.run(society_id, category_name, metrics.get("result", {}))
        except Exception as e:
            out[key] = {"model_name": key, "status": "error", "message": str(e)}

    # 摘要
    out["_summary"] = {
        "society": society_id, "category": category_name,
        "goal": metrics.get("result", {}).get("goal", goal),
        "scope": scope, "strength": strength,
        "data_source": metrics.get("result", {}).get("data_source", ""),
        "approve": metrics.get("result", {}).get("approve", "-"),
        "risk": risk_score,
        "rec_plan": metrics.get("result", {}).get("recPlan", "-"),
        "impact_index": out.get("risk_chain", {}).get("result", {}).get("combined_impact", "-"),
        "models_ok": sum(1 for k in MODELS if out.get(k, {}).get("status") != "error"),
    }
    return out
