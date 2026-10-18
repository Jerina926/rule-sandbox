# -*- coding: utf-8 -*-
"""
虚拟学校社会仿真包
==================

对外暴露 4 个核心入口：
- list_personas() / get_personas_for_content()      : 虚拟人物画像
- list_scales() / get_demographics()                : 人口结构比例
- list_calibration_fields() / compute_calibration() : 本校校准
- run_fusion()                                      : 双源融合

所有人物 / 比例均为虚拟仿真参数，用于挑战杯模拟推演，不代表真实学校数据。
"""

from __future__ import annotations
from typing import List, Dict, Any, Optional, Tuple

from .persona_library import (
    ALL_PERSONAS, PERSONA_BY_ID, CATEGORY_LABEL,
    list_personas, persona_summary_by_category, match_relevance,
)
from .demographics import (
    SCHOOL_SCALES, SCALE_DESCRIPTIONS, list_scales,
    get_demographics, category_totals, ARCHETYPE_BASE,
)
from .school_calibration import (
    CALIBRATION_FIELDS, CALIBRATION_BY_KEY,
    list_calibration_fields, compute_calibrated_proportions, compare_with_default,
)
from .persona_relations import (
    EDGES, CHAIN_TEMPLATES,
    list_edges, list_chain_templates,
    match_edges, match_chains, network_for_content,
)
from .dual_source_fusion import (
    compute_persona_side, build_questionnaire_side,
    normalize_weights, fuse, cohort_breakdown,
)
from .reaction_summary import (
    build_reaction_summary, build_fusion_basis,
)


__all__ = [
    "ALL_PERSONAS", "CATEGORY_LABEL", "SCHOOL_SCALES", "SCALE_DESCRIPTIONS",
    "list_personas", "persona_summary_by_category", "match_relevance",
    "list_scales", "get_demographics", "category_totals",
    "list_calibration_fields", "compute_calibrated_proportions", "compare_with_default",
    "compute_persona_side", "build_questionnaire_side",
    "normalize_weights", "fuse", "cohort_breakdown",
    "EDGES", "CHAIN_TEMPLATES", "list_edges", "list_chain_templates",
    "match_edges", "match_chains", "network_for_content",
    "build_reaction_summary", "build_fusion_basis",
]


def get_personas_for_content(content: str, category_hint: str = "") -> Dict[str, Any]:
    """
    根据发布内容，分类返回人物：
    - strong : 与规则强相关
    - weak   : 同类弱相关
    - dormant: 仅作完整人口库展示
    返回 dict 含 strong / weak / dormant 三个列表 + 总量统计。
    """
    strong: List[Dict[str, Any]] = []
    weak: List[Dict[str, Any]] = []
    dormant: List[Dict[str, Any]] = []
    for p in ALL_PERSONAS:
        rel, score = match_relevance(p, content, category_hint)
        item = p.to_dict()
        item["relevance"] = rel
        item["relevance_score"] = score
        item["stance_label_zh"] = p.stance_label
        if rel == "strong":
            strong.append(item)
        elif rel == "weak":
            weak.append(item)
        else:
            dormant.append(item)
    return {
        "strong": strong,
        "weak": weak,
        "dormant": dormant,
        "counts": {
            "strong": len(strong),
            "weak": len(weak),
            "dormant": len(dormant),
            "total": len(ALL_PERSONAS),
        },
        "category_totals": persona_summary_by_category(),
    }


def run_fusion(
    scale: str,
    calibration: Dict[str, Any],
    metrics: Dict[str, Any],
    questionnaire_data: Optional[Dict[str, Any]] = None,
    weights: Optional[Dict[str, float]] = None,
    base_demographics: Optional[List[Dict[str, Any]]] = None,
    content: str = "",
    category_hint: str = "",
) -> Dict[str, Any]:
    """完整执行：人口比例 → 校准 → 虚拟人物侧 → 问卷侧 → 双源融合 → 群体差异。"""
    # 回退显性化：任何静默回退（默认权重/默认指标值）都记入 fallbacks，随 API 返回对外可见
    fallbacks: List[str] = []

    # 1. 校准后比例
    cal = compute_calibrated_proportions(scale, calibration, base_demographics=base_demographics)

    # 2. 虚拟人物侧
    p_side = compute_persona_side(cal["proportions"], fallbacks=fallbacks)

    # 3. 问卷侧
    q_side = build_questionnaire_side(metrics, questionnaire_data, fallbacks=fallbacks)

    # 4. 归一权重
    w = normalize_weights(weights, fallbacks=fallbacks)

    # 5. 融合
    fused = fuse(q_side, p_side, w)

    # 6. 群体差异
    cohort = cohort_breakdown(cal["proportions"], p_side)

    # 7. 虚拟人物反应摘要（V4.0 新增）
    reaction = build_reaction_summary(p_side)

    # 8. 双源融合依据（V4.0 新增）
    fusion_basis = build_fusion_basis(
        q_side, p_side, fused["fused"], w,
        credibility=cal["credibility"],
        calibration_warnings=cal["warnings"],
        calibration_source_breakdown=cal["source_breakdown"],
    )

    # 9. 人物关系网络（V4.0 新增）
    network = network_for_content(content, category_hint) if content else {"nodes": [], "edges": [], "chains": []}

    return {
        "scale": scale,
        "calibration": {
            "credibility": cal["credibility"],
            "filled_count": cal["filled_count"],
            "total_numeric_fields": cal["total_numeric_fields"],
            "warnings": cal["warnings"],
            "source_breakdown": cal["source_breakdown"],
            "proportions": cal["proportions"],
        },
        "persona_side": p_side,
        "questionnaire_side": q_side,
        "weights": w,
        "fused": fused,
        "cohort": cohort,
        "reaction_summary": reaction,
        "fusion_basis": fusion_basis,
        "persona_network": network,
        "recommended_plan": _recommend_plan(fused["fused"]),
        # 回退显性化：默认值参与融合的完整明细（空列表 = 输入完整有效，未触发任何回退）
        "fallbacks": fallbacks,
        "fallback_note": ("未触发任何数据回退：输入字段完整有效" if not fallbacks
                          else "触发了 %d 处数据回退（详见 fallbacks 明细），相关指标以默认值参与融合"
                               % len(fallbacks)),
    }


def _recommend_plan(fused: Dict[str, float]) -> str:
    if fused["risk_index"] >= 60 or fused["vuln_risk"] >= 70:
        return "限制方案"
    if fused["approve"] >= 70 and fused["oppose"] <= 30 and fused["risk_index"] <= 40:
        return "试点方案"
    if fused["oppose"] >= 50:
        return "温和方案"
    return "原方案"
