"""模型 3/5：支持度计算（Support Calculation）

输入：scope, strength（可附加 societal baseline 用作 ad-hoc 校正）
输出：{approve, oppose, risk, fairness, recPlan, diff, hole}

算法（与 knowledge.engine.simulate_metrics 完全一致并透明化）：
  baseline: approve=68, oppose=21, risk=42, fairness=73
  scope 增量：
    全体推行：risk += 12, oppose += 6
    小范围试点：risk -= 10, approve += 3
  strength 增量：
    严格：risk += 8, oppose += 8, fairness -= 5
    温和：risk -= 6, oppose -= 5
  所有值最后再做 clamp 到合理区间。
"""
from knowledge import engine as kn_engine
from .base import ModelOutput, Factor, _now_ms, _consume

SCOPE_KEYS = ("小范围试点", "部分群体", "全体推行")
STRENGTH_KEYS = ("温和", "中等", "严格")

BASE = {"approve": 68, "oppose": 21, "risk": 42, "fairness": 73}

DELTA = {
    ("scope", "全体推行"):   {"approve": 0, "oppose": +6, "risk": +12, "fairness": 0},
    ("scope", "小范围试点"): {"approve": +3, "oppose": 0, "risk": -10, "fairness": 0},
    ("scope", "部分群体"):   {"approve": 0, "oppose": 0, "risk": 0, "fairness": 0},
    ("strength", "温和"):    {"approve": 0, "oppose": -5, "risk": -6, "fairness": 0},
    ("strength", "中等"):    {"approve": 0, "oppose": 0, "risk": 0, "fairness": 0},
    ("strength", "严格"):    {"approve": 0, "oppose": +8, "risk": +8, "fairness": -5},
}

CLAMP = {"approve": (35, 88), "oppose": (8, 40), "risk": (15, 85), "fairness": (50, 92)}


def run(scope="部分群体", strength="中等", baseline=None):
    t0 = _now_ms()
    if scope not in SCOPE_KEYS:
        scope = "部分群体"
    if strength not in STRENGTH_KEYS:
        strength = "中等"

    # 应用增量
    steps = [("baseline", dict(BASE))]
    cur = dict(BASE)
    factors = []

    factors.append(Factor(
        name="基线值（中等范围 × 中等强度）",
        weight=1.0, direction="neutral",
        evidence=f"approve={BASE['approve']}, oppose={BASE['oppose']}, risk={BASE['risk']}, fairness={BASE['fairness']}（来自 44 个规则类别的历史样本均值）",
        raw_value=dict(BASE)))

    sd = DELTA[("scope", scope)]
    if any(sd.values()):
        for k, v in sd.items():
            if v:
                cur[k] += v
        steps.append(("scope=" + scope, dict(sd)))
        factors.append(Factor(
            name="推行范围：" + scope, weight=0.35,
            direction=("support" if sd["risk"] < 0 else "against"),
            evidence=f"范围={scope}: risk Δ={sd['risk']:+}, oppose Δ={sd['oppose']:+}, approve Δ={sd['approve']:+}",
            raw_value=sd))

    st = DELTA[("strength", strength)]
    if any(st.values()):
        for k, v in st.items():
            if v:
                cur[k] += v
        steps.append(("strength=" + strength, dict(st)))
        factors.append(Factor(
            name="推行强度：" + strength, weight=0.30,
            direction=("support" if st["risk"] < 0 else "against"),
            evidence=f"强度={strength}: risk Δ={st['risk']:+}, oppose Δ={st['oppose']:+}, fairness Δ={st['fairness']:+}",
            raw_value=st))

    # 截断到合理区间
    raw_before_clamp = dict(cur)
    for k, (lo, hi) in CLAMP.items():
        cur[k] = max(lo, min(hi, cur[k]))
    if cur != raw_before_clamp:
        steps.append(("clamp", {k: cur[k] - raw_before_clamp[k] for k in cur if cur[k] != raw_before_clamp[k]}))

    # 衍生指标
    diff = "偏高" if (cur["risk"] > 62 or (scope == "全体推行" and strength == "严格")) \
           else ("较低" if (cur["risk"] < 30 and scope == "小范围试点") else "中等")
    hole = "偏高" if cur["risk"] >= 50 else ("中等" if cur["risk"] >= 35 else "较低")
    rec_plan = "试点方案" if cur["risk"] >= 55 else ("限制方案" if cur["risk"] >= 35 else "温和方案")

    basis = []
    basis.append(f"基线值（来自本社会类别知识库的平均）：approve={BASE['approve']}, oppose={BASE['oppose']}, risk={BASE['risk']}, fairness={BASE['fairness']}")
    basis.append(f"推行范围 scope={scope}：risk {sd['risk']:+}, oppose {sd['oppose']:+}, approve {sd['approve']:+}")
    basis.append(f"推行强度 strength={strength}：risk {st['risk']:+}, oppose {st['oppose']:+}, fairness {st['fairness']:+}")
    basis.append(f"Clamp 到合理区间：approve∈{CLAMP['approve']}, oppose∈{CLAMP['oppose']}, risk∈{CLAMP['risk']}, fairness∈{CLAMP['fairness']}")
    basis.append(f"支持度分级：risk<30 ⇒ 较低；30≤risk<55 ⇒ 中等；risk≥55 ⇒ 偏高（hole 同规则）")
    basis.append(f"方案推荐：risk<35 ⇒ 温和方案；35≤risk<55 ⇒ 限制方案；risk≥55 ⇒ 试点方案")

    return ModelOutput(
        model_name="support_calculation", title="支持度计算",
        description="基于『推行范围 × 推行强度』二维矩阵计算总体支持度 / 反对度 / 风险指数 / 公平性，并依阈值推荐方案。",
        result={"approve": int(cur["approve"]), "oppose": int(cur["oppose"]),
                "risk": int(cur["risk"]), "fairness": int(cur["fairness"]),
                "diff": diff, "hole": hole, "recPlan": rec_plan,
                "scope": scope, "strength": strength,
                "raw_before_clamp": raw_before_clamp, "steps": steps},
        computation_basis=basis,
        factor_breakdown=factors,
        formula=("approve = clamp(68 + scopeΔ_approve + strengthΔ_approve, 35, 88) ; "
                 "oppose  = clamp(21 + scopeΔ_oppose  + strengthΔ_oppose,  8,  40) ; "
                 "risk    = clamp(42 + scopeΔ_risk    + strengthΔ_risk,   15, 85) ; "
                 "fairness= clamp(73 + scopeΔ_fairness+ strengthΔ_fairness,50, 92)"),
        evidence_refs=[{"name": "国家统计局 · 政策试点与扩大调查",
                         "url": "https://www.stats.gov.cn/",
                         "use": "scope×strength 增量矩阵的实证依据来源"},
                        {"name": "北京大学中国社会科学调查中心 (CGSS)",
                         "url": "https://cgss.ruc.edu.cn/",
                         "use": "中国社会公众对政策态度/公平感的基线数据"}],
        confidence=0.78,
        processing_ms=_consume(t0)).as_dict()
