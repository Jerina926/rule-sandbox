# -*- coding: utf-8 -*-
"""
虚拟人物反应摘要 + 双源融合依据
================================

供最终报告 (page-12) 使用，输出 6 类『虚拟人物反应 TOP3』+ 6 项『双源融合依据』。

输入：
- persona_side  : 来自 dual_source_fusion.compute_persona_side()
- fused         : 双源融合结果
- weights       : {"questionnaire": x, "persona": y}
- credibility   : "low" / "medium" / "high"
- cohort_breakdown : 来自 cohort_breakdown()
- persona_breakdown : persona_side["breakdown"]

所有 TOP3 都用『综合得分』排序：attitude + risk_tilt + influence + proportion 等加权。
"""

from __future__ import annotations
from typing import Dict, Any, List, Tuple


def _score_support(row: Dict[str, Any]) -> float:
    return (
        max(0.0, row.get("attitude", 0)) * 1.0
        + row.get("weight_support", 1.0) * 10
        + row.get("proportion", 0.0) * 100
        + (row.get("influence", 1) - 1) * 5
    )


def _score_oppose(row: Dict[str, Any]) -> float:
    return (
        max(0.0, -row.get("attitude", 0)) * 1.0
        + row.get("weight_support", 1.0) * 10
        + row.get("proportion", 0.0) * 100
    )


def _score_risk(row: Dict[str, Any]) -> float:
    rt = row.get("risk_tilt", 0)
    return rt * 25 + row.get("weight_risk", 1.0) * 15 + row.get("proportion", 0.0) * 80


def _score_execution(row: Dict[str, Any]) -> float:
    we = row.get("weight_execution", 0.5)
    # 执行压力和『态度越负 + 风险倾向高』都相关
    return (
        max(0.0, -row.get("attitude", 0)) * 1.0
        + we * 20
        + row.get("risk_tilt", 0) * 8
        + row.get("proportion", 0.0) * 60
    )


def _score_public_opinion(row: Dict[str, Any]) -> float:
    """舆情能力：高 influence + 负面 attitude + 中高 proportion"""
    inf = row.get("influence", 1)
    att = row.get("attitude", 0)
    return inf * 15 + max(0.0, -att) * 0.8 + row.get("proportion", 0.0) * 100


def _score_protection(row: Dict[str, Any]) -> float:
    """需要保护：负态度 + 高 risk + 高 proportion"""
    return (
        max(0.0, -row.get("attitude", 0)) * 1.2
        + row.get("risk_tilt", 0) * 15
        + row.get("proportion", 0.0) * 60
    )


def _topn(breakdown: List[Dict[str, Any]], score_fn, n: int = 3) -> List[Dict[str, Any]]:
    rows = sorted(breakdown, key=score_fn, reverse=True)[:n]
    out: List[Dict[str, Any]] = []
    for r in rows:
        out.append({
            "archetype": r.get("archetype"),
            "score": round(score_fn(r), 2),
            "attitude": r.get("attitude"),
            "risk_tilt": r.get("risk_tilt"),
            "weight_execution": r.get("weight_execution"),
            "proportion": r.get("proportion"),
            "weight_support": r.get("weight_support"),
            "weight_risk": r.get("weight_risk"),
            "influence": r.get("influence"),
        })
    return out


def build_reaction_summary(persona_side: Dict[str, Any]) -> Dict[str, Any]:
    """
    把 persona_side.breakdown 的每一行代入 6 个 scorer，输出 6 个 top3 列表。
    """
    breakdown = persona_side.get("breakdown") or []
    return {
        "most_support": _topn(breakdown, _score_support),
        "most_oppose": _topn(breakdown, _score_oppose),
        "highest_risk": _topn(breakdown, _score_risk),
        "highest_execution_pressure": _topn(breakdown, _score_execution),
        "most_public_opinion": _topn(breakdown, _score_public_opinion),
        "most_need_protection": _topn(breakdown, _score_protection),
        "total_archetypes": len(breakdown),
    }


def build_fusion_basis(
    questionnaire_side: Dict[str, Any],
    persona_side: Dict[str, Any],
    fused: Dict[str, Any],
    weights: Dict[str, float],
    credibility: str,
    calibration_warnings: List[str],
    calibration_source_breakdown: Dict[str, Any],
) -> Dict[str, Any]:
    """
    双源融合推演依据：6 项——问卷来源、人物来源、权重、公式、影响、可信度。
    """
    wq = float(weights.get("questionnaire", 0.6))
    wp = float(weights.get("persona", 0.4))

    # 计算『把权重从 100/0 调到当前』会带来的方向变化
    delta_explain = _weight_change_explanation(persona_side, questionnaire_side, wp)

    return {
        "data_sources": {
            "questionnaire": {
                "is_simulated": questionnaire_side.get("is_simulated", True),
                "description": (
                    "模拟问卷数据：来自 Planner.metrics 的 estimate；"
                    if questionnaire_side.get("is_simulated", True) else
                    "用户导入问卷数据（前端『导入数据』页面提交）"
                ),
                "metrics": {
                    "approve": questionnaire_side.get("approve"),
                    "oppose": questionnaire_side.get("oppose"),
                    "risk_perception": questionnaire_side.get("risk_perception"),
                    "execution_difficulty": questionnaire_side.get("execution_difficulty"),
                    "fairness_perception": questionnaire_side.get("fairness_perception"),
                    "vuln_perception": questionnaire_side.get("vuln_perception"),
                },
            },
            "persona": {
                "description": (
                    "虚拟人物画像 + 人口结构 + 本校校准："
                    "默认 39 人 / 5 大类 / 21 校准字段"
                ),
                "total_personas": 39,
                "categories": ["学生群体", "教师群体", "管理人员", "校园服务人员", "外部相关者"],
                "school_scale": "用户选择",
                "calibration_warnings_count": len(calibration_warnings or []),
                "metrics": {
                    "approve": persona_side.get("approve"),
                    "oppose": persona_side.get("oppose"),
                    "risk_index": persona_side.get("risk_index"),
                    "execution_pressure": persona_side.get("execution_pressure"),
                    "fairness_score": persona_side.get("fairness_score"),
                    "vuln_risk": persona_side.get("vuln_risk"),
                },
            },
        },
        "weight_setting": {
            "questionnaire": round(wq, 4),
            "persona": round(wp, 4),
            "default": "60% 问卷 + 40% 虚拟人物",
            "meaning": (
                "问卷权重越高，结果越接近实际调查反馈；"
                "虚拟人物权重越高，结果越强调人口结构、少数群体、隐藏风险和行为链推演"
            ),
        },
        "formula": {
            "approve": "fused.approve = q.approve × 问卷权重 + p.approve × 人物权重",
            "oppose": "fused.oppose = q.oppose × 问卷权重 + p.oppose × 人物权重",
            "risk_index": "fused.risk = q.risk_perception × 问卷权重 + p.risk_index × 人物权重",
            "execution_difficulty": "fused.execution = q.execution_difficulty × 问卷权重 + p.execution_pressure × 人物权重",
            "fairness_score": "fused.fairness = q.fairness × 问卷权重 + p.fairness_score × 人物权重",
            "vuln_risk": "fused.vuln = q.vuln_perception × 问卷权重 + p.vuln_risk × 人物权重",
            "persona_side_detail": (
                "p.approve = Σ (persona_attitude × proportion × weight_support) / Σ (proportion × weight_support) × 100；"
                "p.risk_index = Σ (risk_tilt × proportion × weight_risk) / 4 / Σ (proportion × weight_risk) × 100；"
                "p.execution = Σ (执行相关 archetype 的 pressure × proportion × weight_execution) × boost；"
                "p.fairness = Σ ((60 + attitude×0.3) × proportion × weight_support) × 100；"
                "p.vuln = Σ (risk_tilt × 晚归/挂科/外宿加权 × proportion × weight_risk) × 25"
            ),
        },
        "weight_change_impact": delta_explain,
        "credibility": {
            "level": credibility,
            "scale_label": {
                "low":    "低 · 仅使用默认模型 + 模拟问卷",
                "medium": "中 · 部分本校数据 + 模拟问卷",
                "high":   "高 · 完整本校数据 + 用户导入问卷",
            }.get(credibility, credibility),
            "source_breakdown": calibration_source_breakdown,
            "calibration_warnings": calibration_warnings or [],
            "disclaimer": (
                "数据可信度说明：默认参数仅用于模拟推演，不代表真实学校情况；"
                "用户可手动填写本校数据或导入问卷以提高可信度"
            ),
        },
    }


def _weight_change_explanation(
    persona_side: Dict[str, Any],
    questionnaire_side: Dict[str, Any],
    persona_weight: float,
) -> str:
    """
    描述：当前虚拟人物权重相对『纯问卷（0% 人物）』的差异方向。
    """
    wp = persona_weight
    if wp >= 0.7:
        return (
            "由于用户将虚拟人物权重调高至 {wp:.0%}，系统更加重视"
            "宿管人员、作息规律学生和高风险晚归学生等执行/风险行为链条；"
            "因此风险指数与漏洞风险显著高于纯问卷结果"
        ).format(wp=wp)
    if wp >= 0.5:
        return (
            "用户将虚拟人物权重设为 {wp:.0%}，结果均衡参考问卷与人物画像；"
            "问卷结果反映『被访者主观表达』，人物结果补足『少数群体 + 隐藏行为链』"
        ).format(wp=wp)
    if wp >= 0.3:
        return (
            "用户将虚拟人物权重设为 {wp:.0%}，结果以问卷为主、人物为辅；"
            "人物维度用于补全常被问卷忽略的执行难度与漏洞风险"
        ).format(wp=wp)
    return (
        "用户将虚拟人物权重调低至 {wp:.0%}，系统更接近问卷数据本身；"
        "人物画像仅作为参考背景，对最终结果影响较小"
    ).format(wp=wp)
