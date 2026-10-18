# -*- coding: utf-8 -*-
"""
双源融合推演模型
================

让最终分析结果由『问卷数据』和『虚拟人物画像』共同决定。
用户可调整二者权重（默认 60% 问卷 + 40% 虚拟人物，总和恒为 100%）。

6 项融合指标：
1. 最终支持度   = 问卷支持度 × 问卷权重 + 虚拟人物支持度 × 虚拟人物权重
2. 最终反对度   = 问卷反对度 × 问卷权重 + 虚拟人物反对度 × 虚拟人物权重
3. 最终风险指数 = 问卷风险感知 × 问卷权重 + 虚拟人物风险指数 × 虚拟人物权重
4. 最终执行难度 = 问卷执行难度 × 问卷权重 + 虚拟人物执行压力 × 虚拟人物权重
5. 最终公平性   = 问卷公平感知 × 问卷权重 + 虚拟人物公平评分 × 虚拟人物权重
6. 最终漏洞风险 = 问卷漏洞感知 × 问卷权重 + 虚拟人物高风险行为倾向 × 虚拟人物权重

输入：
- q_data   : 问卷侧数据
  - approve, oppose, risk_perception, execution_difficulty, fairness_perception, vuln_perception
- v_data   : 虚拟人物侧数据
  - approve, oppose, risk_index, execution_pressure, fairness_score, vuln_risk
- weights  : {"questionnaire": 0.6, "persona": 0.4}
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, List, Optional

from .demographics import ARCHETYPE_BASE, _attitude_by_archetype
from .persona_library import ALL_PERSONAS


# ---------------------------------------------------------------------------
# 虚拟人物侧计算
# ---------------------------------------------------------------------------

def compute_persona_side(
    proportions: Dict[str, float],
    risk_tilt_by_archetype: Optional[Dict[str, int]] = None,
    pressure_boost: float = 1.0,
    fallbacks: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    根据人群比例 + 态度 + 风险倾向 + 执行压力权重，计算虚拟人物侧 6 项指标。

    公式：
    - 人物支持度 = Σ (persona_attitude × proportion × weight_support) / Σ (proportion × weight_support) × 100
    - 人物风险指数 = Σ (risk_tilt × proportion × weight_risk) / 4 / Σ (proportion × weight_risk) × 100
    - 人物执行压力 = Σ (执行相关 archetype 的 pressure × proportion × weight_execution) × pressure_boost
    - 人物公平性 = Σ ((1 - 反对度 / 100) × proportion × weight_support) × 100
    - 人物漏洞风险 = Σ (risk_tilt × often_late_factor × proportion × weight_risk)
    """
    risk_map: Dict[str, int] = {}
    if risk_tilt_by_archetype:
        risk_map.update(risk_tilt_by_archetype)
    for p in ALL_PERSONAS:
        if p.archetype not in risk_map:
            risk_map[p.archetype] = p.risk_tilt

    # 初始化累计
    s_num = 0.0; s_den = 0.0
    o_num = 0.0; o_den = 0.0
    r_num = 0.0; r_den = 0.0
    e_num = 0.0; e_den = 0.0
    f_num = 0.0; f_den = 0.0
    v_num = 0.0; v_den = 0.0

    per_archetype_breakdown: List[Dict[str, Any]] = []

    for arch, p in proportions.items():
        attitude = _attitude_by_archetype(arch)
        rt = risk_map.get(arch, 0)
        base = ARCHETYPE_BASE.get(arch, {})
        ws = base.get("w_s", 1.0)
        wr = base.get("w_r", 0.5)
        we = base.get("w_e", 0.5)

        # 支持度（-100~+100 → 0~100）
        approve_v = (attitude + 100) / 2.0
        oppose_v = 100 - approve_v
        # 风险指数（0~4 → 0~100）
        risk_v = (rt / 4.0) * 100
        # 执行压力：把 attitude 转成『压力』（反对 + 风险）
        exec_v = max(0.0, (-attitude + rt * 25))
        # 公平性：基础 60，按态度浮动
        fair_v = max(0.0, min(100.0, 60 + attitude * 0.3))
        # 漏洞风险：高风险 archetype 加权
        often_late_factor = 1.5 if "晚归" in arch or "挂科" in arch or "外宿" in arch else 1.0
        vuln_v = rt * wr * often_late_factor * 25

        s_num += approve_v * p * ws
        s_den += p * ws
        o_num += oppose_v * p * ws
        o_den += p * ws
        r_num += risk_v * p * wr
        r_den += p * wr
        e_num += exec_v * p * we
        e_den += p * we
        f_num += fair_v * p * ws
        f_den += p * ws
        v_num += vuln_v * p
        v_den += p

        per_archetype_breakdown.append({
            "archetype": arch,
            "proportion": round(p, 4),
            "attitude": attitude,
            "risk_tilt": rt,
            "weight_support": ws,
            "weight_risk": wr,
            "weight_execution": we,
            "approve_contrib": round(approve_v, 2),
            "risk_contrib": round(risk_v, 2),
            "execution_contrib": round(exec_v, 2),
            "vuln_contrib": round(vuln_v, 2),
        })

    persona_approve = (s_num / s_den) if s_den > 0 else 50.0
    persona_oppose = (o_num / o_den) if o_den > 0 else 50.0
    persona_risk = (r_num / r_den) if r_den > 0 else 30.0
    persona_exec = (e_num / e_den) * pressure_boost if e_den > 0 else 30.0
    persona_fair = (f_num / f_den) if f_den > 0 else 60.0
    persona_vuln = (v_num / v_den) if v_den > 0 else 30.0

    # 回退显性化：人群比例为空或权重合计为 0 时，上述默认值实际参与计算，必须对外可见
    if fallbacks is not None and any(d <= 0 for d in (s_den, o_den, r_den, e_den, f_den, v_den)):
        fallbacks.append(
            "persona_side：人群比例为空或权重合计为 0，六项指标（支持/反对/风险/执行压力/公平/漏洞）"
            "回退默认值 50/50/30/30/60/30")

    # 归一到 0~100
    persona_exec = max(0.0, min(100.0, persona_exec))

    return {
        "approve": round(persona_approve, 1),
        "oppose": round(persona_oppose, 1),
        "risk_index": round(persona_risk, 1),
        "execution_pressure": round(persona_exec, 1),
        "fairness_score": round(persona_fair, 1),
        "vuln_risk": round(persona_vuln, 1),
        "breakdown": per_archetype_breakdown,
    }


# ---------------------------------------------------------------------------
# 问卷侧：默认模拟数据（来自 analysis.metrics + questionnaire）
# ---------------------------------------------------------------------------

def build_questionnaire_side(metrics: Dict[str, Any], questionnaire_data: Dict[str, Any] = None,
                             fallbacks: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    根据 Planner 的 metrics 构造问卷侧数据。如有真实问卷数据则合并覆盖。
    缺失 / 非数值字段回退默认值，并将回退明细写入 fallbacks（显性可见）。
    """
    key_map = [("approve", "approve", 50), ("oppose", "oppose", 30),
               ("risk", "risk_perception", 35), ("diff", "execution_difficulty", 40),
               ("fair", "fairness_perception", 70), ("vuln", "vuln_perception", 30)]
    q: Dict[str, Any] = {"is_simulated": True}
    bad = []
    for src_key, dst_key, dv in key_map:
        val = metrics.get(src_key) if isinstance(metrics, dict) else None
        ok = False
        if val is not None:
            try:
                f = float(val) if not isinstance(val, bool) else float(dv)
                if f == f:  # 非 NaN
                    q[dst_key] = f
                    ok = True
            except Exception:
                pass
        if not ok:
            q[dst_key] = float(dv)
            bad.append(src_key)
    if bad and fallbacks is not None:
        fallbacks.append("questionnaire_side：指标 %s 缺失或非数值，已回退默认值" % "、".join(bad))
    if questionnaire_data:
        for dst_key in ("approve", "oppose", "risk_perception", "execution_difficulty",
                        "fairness_perception", "vuln_perception"):
            v = questionnaire_data.get(dst_key)
            if v is None:
                continue
            try:
                f = float(v) if not isinstance(v, bool) else None
                if f is not None and f == f:
                    q[dst_key] = f
                else:
                    if fallbacks is not None:
                        fallbacks.append("questionnaire_side：导入问卷字段 %s 非法（%r），未覆盖模拟值" % (dst_key, v))
            except Exception:
                if fallbacks is not None:
                    fallbacks.append("questionnaire_side：导入问卷字段 %s 非法（%r），未覆盖模拟值" % (dst_key, v))
        if questionnaire_data.get("source") == "user_imported":
            q["is_simulated"] = False
    return q


# ---------------------------------------------------------------------------
# 双源融合
# ---------------------------------------------------------------------------

def normalize_weights(weights: Optional[Dict[str, float]],
                      fallbacks: Optional[List[str]] = None) -> Dict[str, float]:
    """
    确保问卷 + 虚拟人物权重总和为 1。
    默认 0.6 + 0.4。
    """
    if not weights:
        if fallbacks is not None:
            fallbacks.append("weights：未提供权重，回退默认 60% 问卷 + 40% 虚拟人物")
        return {"questionnaire": 0.6, "persona": 0.4}
    try:
        q = float(weights.get("questionnaire", 0.6))
        p = float(weights.get("persona", 0.4))
    except Exception:
        q, p = 0.0, 0.0
    # 若总和为 0 或非数，回退默认
    s = q + p
    if s <= 0 or s != s:  # NaN 保护
        if fallbacks is not None:
            fallbacks.append("weights：权重缺失或非法（总和≤0 或 NaN），回退默认 60% 问卷 + 40% 虚拟人物")
        return {"questionnaire": 0.6, "persona": 0.4}
    return {"questionnaire": round(q / s, 4), "persona": round(p / s, 4)}


def fuse(q_side: Dict[str, Any], p_side: Dict[str, Any], weights: Dict[str, float]) -> Dict[str, Any]:
    """
    6 项指标双源融合。
    """
    wq = weights.get("questionnaire", 0.6)
    wp = weights.get("persona", 0.4)

    def f(a, b):
        return round(a * wq + b * wp, 1)

    fused = {
        "approve": f(q_side["approve"], p_side["approve"]),
        "oppose": f(q_side["oppose"], p_side["oppose"]),
        "risk_index": f(q_side["risk_perception"], p_side["risk_index"]),
        "execution_difficulty": f(q_side["execution_difficulty"], p_side["execution_pressure"]),
        "fairness_score": f(q_side["fairness_perception"], p_side["fairness_score"]),
        "vuln_risk": f(q_side["vuln_perception"], p_side["vuln_risk"]),
    }

    # 解释（一句话）
    explanation = _build_explanation(weights, p_side)

    return {
        "fused": fused,
        "weights": weights,
        "questionnaire_side": q_side,
        "persona_side": p_side,
        "weight_explanation": explanation,
    }


def _build_explanation(weights: Dict[str, float], p_side: Dict[str, Any]) -> str:
    wp = weights.get("persona", 0.4) * 100
    if wp >= 70:
        prefix = f"由于用户将虚拟人物权重调高至 {wp:.0f}%，系统更加重视宿管人员、作息规律学生和高风险晚归学生的行为影响"
    elif wp >= 50:
        prefix = f"用户将虚拟人物权重设为 {wp:.0f}%，结果均衡参考问卷与人物画像"
    elif wp >= 30:
        prefix = f"用户将虚拟人物权重设为 {wp:.0f}%，结果以问卷数据为主、人物画像为辅"
    else:
        prefix = f"由于用户将虚拟人物权重调低至 {wp:.0f}%，系统更接近问卷数据本身"
    return prefix + "，因此风险指数相对问卷结果出现显著调整。"


# ---------------------------------------------------------------------------
# 群体差异：基于虚拟人物侧 + 问卷侧融合
# ---------------------------------------------------------------------------

def cohort_breakdown(proportions: Dict[str, float], persona_side: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    返回 5 大类的支持度 / 反对度 / 风险倾向 / 影响力汇总。
    用于前端『人口结构饼图 + 重点人群占比 + 关键群体分析』。
    """
    cats: Dict[str, Dict[str, Any]] = {}
    for row in persona_side["breakdown"]:
        arch = row["archetype"]
        # 反查 category（从 demographics）
        from .demographics import _category_by_archetype
        cat = _category_by_archetype(arch)
        if cat not in cats:
            cats[cat] = {"proportion": 0.0, "approve_weighted": 0.0, "risk_weighted": 0.0,
                          "execution_weighted": 0.0, "vuln_weighted": 0.0, "count_archetypes": 0}
        c = cats[cat]
        c["proportion"] += row["proportion"]
        c["approve_weighted"] += row["approve_contrib"] * row["proportion"]
        c["risk_weighted"] += row["risk_contrib"] * row["proportion"]
        c["execution_weighted"] += row["execution_contrib"] * row["proportion"]
        c["vuln_weighted"] += row["vuln_contrib"] * row["proportion"]
        c["count_archetypes"] += 1

    out = []
    for cat, c in cats.items():
        out.append({
            "category": cat,
            "proportion": round(c["proportion"], 4),
            "approve_avg": round(c["approve_weighted"] / max(c["proportion"], 1e-6), 1),
            "risk_avg": round(c["risk_weighted"] / max(c["proportion"], 1e-6), 1),
            "execution_avg": round(c["execution_weighted"] / max(c["proportion"], 1e-6), 1),
            "vuln_avg": round(c["vuln_weighted"] / max(c["proportion"], 1e-6), 1),
            "archetype_count": c["count_archetypes"],
        })
    out.sort(key=lambda x: x["proportion"], reverse=True)
    return out
