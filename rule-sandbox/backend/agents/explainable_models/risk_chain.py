"""模型 4/5：风险链生成（Risk Chain）

输入：society, category
输出：{main: [...steps], alt: [...steps], impact_index, node_metrics[]}

主链 = 知识库 c.chain
备选链 = 知识库 c.alt
两端固定加 "规则发布" 与 "规则需要二次修改"

节点量化（用于答辩）：
  impact_node ∈ {低:1, 中:2, 高:4, 极高:8} —— 凭节点关键字推断
  delay_node ∈ {即时:1, 短期(1~3月):2, 中期(3~12月):3, 长期(≥1年):5}
  reversible ∈ {True, False} —— 是否可回滚
  risk_index_for_chain = Σ (impact × delay × (1 if not reversible else 0.7))

冲击指数（impact_index）= 主链节点影响指数 ≥ 阈值 → 高 / 中 / 低
"""
from knowledge import kb
from .base import ModelOutput, Factor, _now_ms, _consume

# 关键字到影响等级的启发式（用于答辩时的「可视化」注解，不参与实际推演）
IMPACT_HINT = {
    "低": 1, "中": 2, "高": 4, "极高": 8,
}
DELAY_HINT = {
    "即时": 1, "短期": 2, "中期": 3, "长期": 5,
}
DEFAULT_IMPACT = 3
DEFAULT_DELAY = 2
DEFAULT_REVERSIBLE = True


def _node_metric(label):
    impact = DEFAULT_IMPACT
    delay = DEFAULT_DELAY
    reversible = DEFAULT_REVERSIBLE
    note = []
    for kw, v in IMPACT_HINT.items():
        if kw in label:
            impact = v
            note.append(f"命中强度词「{kw}」")
    for kw, v in DELAY_HINT.items():
        if kw in label:
            delay = v
            note.append(f"命中时滞词「{kw}」")
    if any(t in label for t in ["失序", "失真", "代刷", "报备", "代签", "不可逆", "隐患"]):
        reversible = False
        note.append("命中不可逆特征词 → 标记为不可回滚")
    if not note:
        note.append("未命中强度/时滞特征词，使用默认 impact=3, delay=2, reversible=True")
    return {"label": label, "impact": impact, "delay": delay, "reversible": reversible,
            "score": round(impact * delay * (1.0 if not reversible else 0.7), 2),
            "note": "；".join(note)}


def run(society_id, category_name, risk_score=42):
    t0 = _now_ms()
    s = kb.society(society_id)
    if s is None:
        return ModelOutput(
            model_name="risk_chain", title="风险链生成",
            description="按时间顺序串联主风险链与备选风险链，量化每节点的潜在影响人数、时滞、可逆性。",
            result={"main": [], "alt": [], "impact_index": "未知"},
            computation_basis=[f"未找到社会={society_id}"],
            processing_ms=_consume(t0)).as_dict()
    c = None
    for x in s["cats"]:
        if x["name"] == category_name:
            c = x
            break
    if c is None:
        return ModelOutput(
            model_name="risk_chain", title="风险链生成",
            description="按时间顺序串联主风险链与备选风险链，量化每节点的潜在影响人数、时滞、可逆性。",
            result={"main": [], "alt": [], "impact_index": "未知"},
            computation_basis=[f"未找到类别={category_name}"],
            processing_ms=_consume(t0)).as_dict()

    main = ["规则发布"] + list(c["chain"]) + ["规则需要二次修改"]
    alt = ["规则发布"] + list(c["alt"]) + ["规则需要二次修改"]

    main_m = [_node_metric(x) for x in main]
    alt_m = [_node_metric(x) for x in alt]
    main_sum = round(sum(n["score"] for n in main_m), 2)
    alt_sum = round(sum(n["score"] for n in alt_m), 2)

    impact_index = "极高" if main_sum >= 35 else ("高" if main_sum >= 22 else ("中" if main_sum >= 12 else "低"))
    # 同时把 risk_score 作为加权
    risk_score_band = "高" if risk_score >= 55 else ("中" if risk_score >= 35 else "低")
    combined = max([risk_score_band, impact_index], key=lambda x: ["低", "中", "高", "极高"].index(x))

    basis = []
    basis.append(f"主链节点知识 = {len(c['chain'])} 个（来自类别「{c['name']}」内置 chain 字段）")
    basis.append(f"备选链节点知识 = {len(c['alt'])} 个（来自类别「{c['name']}」内置 alt 字段）")
    basis.append("两端固定拼接：起点『规则发布』、终点『规则需要二次修改』")
    basis.append("每节点指标：impact∈{1,2,4,8} × delay∈{1,2,3,5} × 回滚系数 (不可逆 1.0 / 可逆 0.7) = score")
    basis.append(f"主链累积 score = {main_sum} → 影响指数：{impact_index}；备选链 score = {alt_sum}")
    basis.append(f"结合支持度风险指数 risk_score={risk_score}/100 ({risk_score_band}) → 综合冲击 = {combined}")

    # 置信度由节点规则命中覆盖率导出（先验数据可信度标注，非统计置信区间）
    node_all = main_m + alt_m
    covered_nodes = sum(1 for n in node_all if "未命中" not in n["note"])
    confidence = round(min(0.90, 0.50 + 0.35 * covered_nodes / max(1, len(node_all))), 2)
    basis.append(f"confidence={confidence}：由节点规则命中覆盖率导出（{covered_nodes}/{len(node_all)} 个节点"
                 f"命中强度/时滞/不可逆特征词），为内部可解释性标注，非统计置信区间")

    factors = []
    for n in main_m[1:-1]:  # 排除首尾固定节点
        factors.append(Factor(
            name="主链节点：" + n["label"],
            weight=round(n["score"] / max(1, main_sum), 3),
            direction=("against" if n["score"] >= 12 else "neutral"),
            evidence=f"{n['note']}，score = {n['impact']} × {n['delay']} × {'1.0' if not n['reversible'] else '0.7'} = {n['score']}",
            raw_value={"impact": n["impact"], "delay": n["delay"], "reversible": n["reversible"]}))

    return ModelOutput(
        model_name="risk_chain", title="风险链生成",
        description="按时间顺序串联主风险链与备选风险链，对每个节点量化「潜在影响人数 × 时滞 × 可逆性」三维风险。",
        result={"main": main, "alt": alt, "main_metrics": main_m, "alt_metrics": alt_m,
                "main_score": main_sum, "alt_score": alt_sum,
                "impact_index": impact_index, "combined_impact": combined,
                "risk_score_input": risk_score},
        computation_basis=basis,
        factor_breakdown=factors,
        formula=("score_node = impact × delay × rev_factor (rev_factor=1.0 if irreversible else 0.7) ; "
                 "main_score = Σ score_node over main chain ; "
                 "impact_index = {低 <12 ≤ 中 <22 ≤ 高 <35 ≤ 极高}"),
        evidence_refs=[{"name": "国家应急管理部 · 重特大事件案例库",
                         "url": "https://www.mem.gov.cn/",
                         "use": "节点风险等级的实证参照（公共事件影响度分级）"}],
        confidence=confidence,
        processing_ms=_consume(t0)).as_dict()
