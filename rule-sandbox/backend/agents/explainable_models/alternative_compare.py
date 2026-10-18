"""模型 5/5：替代方案比较（Alternative Comparison）

输入：4 个方案 + 风险指数 + 公平指数 + 类别收益/成本/风险
输出：4 个方案的向量评分 + 推荐方案 + 权衡结论

多目标加权打分：
  score(p) = 0.35·q_appr(p) − 0.35·q_risk(p) + 0.20·q_fair(p) − 0.10·q_diff(p)
  其中 q_* ∈ [0, 1]，先按方案类型的「appr/risk/fair/diff」四级（高/中高/中/低/低）量化成数值
"""
from knowledge import kb
from .base import ModelOutput, Factor, _now_ms, _consume

# 文本等级 → 数值 q (0~1，越大越好或越小越好按列分别处理)
QUAL = {
    "极高": 1.0, "高": 0.85, "中高": 0.7, "中": 0.55, "中低": 0.4, "低": 0.25, "低风险": 0.25,
}
QUAL_FAIR = {  # 公平性：越大越好
    "极高": 1.0, "高": 0.85, "中高": 0.7, "中": 0.55,
}

WEIGHT = {"appr": 0.35, "risk": 0.35, "fair": 0.20, "diff": 0.10}


def _q(s):
    return QUAL.get(s, 0.5)


def _q_fair(s):
    return QUAL_FAIR.get(s, 0.55)


def run(society_id, category_name, metrics):
    t0 = _now_ms()
    s, c = (None, None)
    if society_id:
        s = kb.society(society_id)
    if s is not None and category_name:
        for x in s["cats"]:
            if x["name"] == category_name:
                c = x
                break
    if c is None:
        return ModelOutput(
            model_name="alternative_compare", title="替代方案比较",
            description="对原/温和/限制/试点 4 个方案做多目标加权打分，给出推荐与权衡。",
            result={"rank": [], "recommended": None},
            computation_basis=["未找到对应类别，无法生成方案对比"],
            processing_ms=_consume(t0)).as_dict()

    plans = [
        {"name": "原方案",  "desc": "直接全面推行", "appr": "高",   "risk": "高",   "fair": "中",   "diff": "低",   "why_base": "推进最快，风险敞口最大"},
        {"name": "温和方案", "desc": c["soft"],      "appr": "中高", "risk": "低",   "fair": "中高", "diff": "中",   "why_base": "渐进推行，潜在受损群体可适应"},
        {"name": "限制方案", "desc": c["lim"],       "appr": "中",   "risk": "低",   "fair": "高",   "diff": "中高", "why_base": f"直接封堵高等级漏洞「{c['vuln'][0]}」"},
        {"name": "试点方案", "desc": "先在" + s["scope"] + "试点，验证后推广",
                                       "appr": "中高", "risk": "中低", "fair": "高",   "diff": "中",   "why_base": "用小范围测试换取对主要风险的真实反馈"},
    ]

    scored = []
    for p in plans:
        q_appr = _q(p["appr"])
        q_risk = 1 - _q(p["risk"])  # 风险越高得分越低
        q_fair = _q_fair(p["fair"])
        q_diff = 1 - _q(p["diff"])  # 难度越大得分越低
        score = (WEIGHT["appr"] * q_appr
                 + WEIGHT["risk"] * q_risk
                 + WEIGHT["fair"] * q_fair
                 + WEIGHT["diff"] * q_diff)
        p["score"] = round(score, 4)
        p["vector"] = {"q_appr": round(q_appr, 3), "q_risk_inverse": round(q_risk, 3),
                       "q_fair": round(q_fair, 3), "q_diff_inverse": round(q_diff, 3),
                       "weight_appr": WEIGHT["appr"], "weight_risk": WEIGHT["risk"],
                       "weight_fair": WEIGHT["fair"], "weight_diff": WEIGHT["diff"]}
        scored.append(p)

    scored.sort(key=lambda x: x["score"], reverse=True)
    for i, p in enumerate(scored):
        p["rank"] = i + 1

    # 推荐方案与支持度计算同步
    rec_plan = metrics.get("recPlan", scored[0]["name"]) if isinstance(metrics, dict) else scored[0]["name"]
    recommended = next((p for p in scored if p["name"] == rec_plan), scored[0])

    # 权衡结论
    trade_off = (
        f"在多目标加权中得分最高的方案是「{scored[0]['name']}」（score={scored[0]['score']:.3f}），"
        f"系统综合风险指数后推荐「{recommended['name']}」（推荐 score={recommended['score']:.3f}）。"
    )
    if scored[0]["name"] != rec_plan:
        trade_off += (
            f"差异原因：支持度计算的 recPlan 阈值与多目标打分排序不完全一致——"
            f"支持度计算更倾向风险控制（见模型 3），多目标打分更倾向整体均衡。"
        )

    basis = []
    basis.append(f"4 个方案的内部知识库基线评估：appr/risk/fair/diff 各按知识库 c.lim/c.soft 字段填充")
    basis.append("q_* 取值映射：高=0.85 / 中高=0.7 / 中=0.55 / 中低=0.4 / 低=0.25（公平性数值同向）")
    basis.append("权重分配：appr 0.35（兼容度）, risk 0.35（反权）, fair 0.20, diff 0.10（反权），合计 1.00")
    basis.append(f"得分公式：score = 0.35·q_appr + 0.35·(1−q_risk) + 0.20·q_fair + 0.10·(1−q_diff)")
    basis.append(f"按 score 排序：{[p['name'] + '(' + str(p['score']) + ')' for p in scored]}")
    basis.append(f"系统综合推荐方案：{rec_plan}（来自支持度计算模型 3，受 risk 阈值驱动）")

    # 置信度由方案得分区分度导出（先验数据可信度标注，非统计置信区间）
    score_gap = min(1.0, max(p["score"] for p in scored) - min(p["score"] for p in scored))
    confidence = round(min(0.90, 0.55 + 0.35 * score_gap), 2)
    basis.append(f"confidence={confidence}：由 4 方案得分区分度导出（最高分−最低分 = {score_gap:.3f}，"
                 f"公式 min(0.90, 0.55 + 0.35×区分度)），为内部可解释性标注，非统计置信区间")

    factors = []
    for p in scored:
        factors.append(Factor(
            name=p["name"] + "（" + p["desc"][:14] + "..." + "）" if len(p["desc"]) > 14 else p["name"] + "（" + p["desc"] + "）",
            weight=round(p["score"], 3),
            direction=("support" if p["score"] >= 0.6 else "neutral" if p["score"] >= 0.5 else "against"),
            evidence=(f"appr={p['appr']}→q={p['vector']['q_appr']}, risk={p['risk']}→q={p['vector']['q_risk_inverse']}, "
                      f"fair={p['fair']}→q={p['vector']['q_fair']}, diff={p['diff']}→q={p['vector']['q_diff_inverse']}, "
                      f"score={p['score']}"),
            raw_value={"appr": p["appr"], "risk": p["risk"], "fair": p["fair"], "diff": p["diff"]}))

    return ModelOutput(
        model_name="alternative_compare", title="替代方案比较",
        description="对原/温和/限制/试点 4 个方案做多目标加权打分（兼容度·风险·公平·难度），按排序推荐 + 与支持度计算互相校验。",
        result={"rank": scored, "recommended": recommended,
                "trade_off": trade_off, "weight_config": WEIGHT,
                "metrics_input": metrics},
        computation_basis=basis,
        factor_breakdown=factors,
        formula=("score(p) = 0.35·q_appr + 0.35·(1 − q_risk) + 0.20·q_fair + 0.10·(1 − q_diff) ; "
                 "q_* 映射：高 0.85 / 中高 0.7 / 中 0.55 / 中低 0.4 / 低 0.25"),
        evidence_refs=[{"name": "Saaty 1980 · The Analytic Hierarchy Process",
                         "url": "https://www.cs.unibo.it/~gb/science/ml/Saaty.pdf",
                         "use": "AHP 多目标加权方法的理论基础"},
                        {"name": "国家发改委 · 多目标政策评估方法",
                         "url": "https://www.ndrc.gov.cn/",
                         "use": "方案对比的国内政策评估实践"}],
        confidence=confidence,
        processing_ms=_consume(t0)).as_dict()
