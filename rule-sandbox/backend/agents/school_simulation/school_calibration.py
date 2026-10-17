# -*- coding: utf-8 -*-
"""
本校校准模式
============

允许用户输入或导入本校基础数据，自动重新计算各类人群比例与权重，
并在结果中标注『该项为系统估计值』/『数据可信度』。

校准字段（20+）：
- school_name            : 学校名称
- school_scale           : 学校规模（小型学院 / 普通本科高校 / 综合性大学 / 住宿制高校 / 职业院校）
- total_students         : 在校生总数
- undergrad_count        : 本科生人数
- grad_count             : 研究生人数
- intl_count             : 留学生人数
- dorm_students          : 住校学生人数
- dorm_ratio             : 住校比例（0~1）
- commuter_count         : 走读学生人数
- teacher_count          : 教师人数
- counselor_count        : 辅导员人数
- admin_count            : 行政人员人数
- dorm_staff_count       : 宿管人员人数
- security_count         : 保卫处/安保人员人数
- canteen_staff_count    : 食堂/后勤人员人数
- clinic_staff_count     : 校医院人员人数
- cadre_ratio            : 学生干部比例
- club_ratio             : 社团活跃学生比例
- grad_entrance_ratio    : 考研学生比例
- often_late_ratio       : 经常晚归学生比例
- regular_ratio          : 作息规律学生比例
- parent_attention       : 家长关注强度（0~1）
- campus_public_opinion  : 校园舆情活跃度（0~1）

三种数据输入方式：
- default     : 系统默认（基于 school_scale 的默认人口结构）
- manual      : 用户手动填写
- csv_excel   : 用户导入（前端解析后按字段传入）
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional

from .demographics import (
    SCHOOL_SCALES,
    SCALE_PROPORTION,
    ARCHETYPE_BASE,
    get_demographics,
    _attitude_by_archetype,
    _category_by_archetype,
    _first_persona_by_archetype,
)


# 校准字段定义
CALIBRATION_FIELDS: List[Dict[str, Any]] = [
    # 基础信息
    {"key": "school_name",            "label": "学校名称",                 "type": "text",  "required": False, "group": "基础信息"},
    {"key": "school_scale",           "label": "学校规模",                 "type": "select", "required": True,  "group": "基础信息",
     "options": SCHOOL_SCALES, "default": "普通本科高校"},
    # 人数字段
    {"key": "total_students",         "label": "在校生总数",               "type": "number", "required": False, "group": "人数统计"},
    {"key": "undergrad_count",        "label": "本科生人数",               "type": "number", "required": False, "group": "人数统计"},
    {"key": "grad_count",             "label": "研究生人数",               "type": "number", "required": False, "group": "人数统计"},
    {"key": "intl_count",             "label": "留学生人数",               "type": "number", "required": False, "group": "人数统计"},
    {"key": "dorm_students",          "label": "住校学生人数",             "type": "number", "required": False, "group": "人数统计"},
    {"key": "dorm_ratio",             "label": "住校比例",                 "type": "ratio",  "required": False, "group": "人数统计"},
    {"key": "commuter_count",         "label": "走读学生人数",             "type": "number", "required": False, "group": "人数统计"},
    {"key": "teacher_count",          "label": "教师人数",                 "type": "number", "required": False, "group": "人数统计"},
    {"key": "counselor_count",        "label": "辅导员人数",               "type": "number", "required": False, "group": "人数统计"},
    {"key": "admin_count",            "label": "行政人员人数",             "type": "number", "required": False, "group": "人数统计"},
    {"key": "dorm_staff_count",       "label": "宿管人员人数",             "type": "number", "required": False, "group": "人数统计"},
    {"key": "security_count",         "label": "保卫处/安保人员人数",       "type": "number", "required": False, "group": "人数统计"},
    {"key": "canteen_staff_count",    "label": "食堂/后勤人员人数",         "type": "number", "required": False, "group": "人数统计"},
    {"key": "clinic_staff_count",     "label": "校医院人员人数",           "type": "number", "required": False, "group": "人数统计"},
    # 比例字段
    {"key": "cadre_ratio",            "label": "学生干部比例",             "type": "ratio",  "required": False, "group": "群体比例"},
    {"key": "club_ratio",             "label": "社团活跃学生比例",         "type": "ratio",  "required": False, "group": "群体比例"},
    {"key": "grad_entrance_ratio",    "label": "考研学生比例",             "type": "ratio",  "required": False, "group": "群体比例"},
    {"key": "often_late_ratio",       "label": "经常晚归学生比例",         "type": "ratio",  "required": False, "group": "群体比例"},
    {"key": "regular_ratio",          "label": "作息规律学生比例",         "type": "ratio",  "required": False, "group": "群体比例"},
    # 强度字段
    {"key": "parent_attention",       "label": "家长关注强度",             "type": "ratio",  "required": False, "group": "舆情强度"},
    {"key": "campus_public_opinion",  "label": "校园舆情活跃度",           "type": "ratio",  "required": False, "group": "舆情强度"},
]


CALIBRATION_BY_KEY: Dict[str, Dict[str, Any]] = {f["key"]: f for f in CALIBRATION_FIELDS}


# ---------------------------------------------------------------------------
# 校准计算
# ---------------------------------------------------------------------------

# 每个校准字段会调整哪些 archetype 的比例
# 数值表示『线性缩放系数』（1.0 表示不变）
ARCHETYPE_FIELD_SCALARS: Dict[str, Dict[str, float]] = {
    "dorm_ratio": {
        # 住校比例影响『住校属性』相关 archetype
        "普通住校生": 1.5, "大一新生": 1.3, "毕业生": 0.8, "考研学生": 1.0,
        "作息规律学生": 1.2, "走读生": 0.5,
    },
    "cadre_ratio":     {"学生干部": 2.5},
    "club_ratio":      {"社团活跃学生": 2.5},
    "grad_entrance_ratio": {"考研学生": 2.0},
    "often_late_ratio": {"经常晚归学生": 3.0, "挂科风险学生": 1.3},
    "regular_ratio":   {"作息规律学生": 2.5},
    "intl_count":      {"留学生": 1.5},
    "grad_count":      {"毕业生": 1.4, "导师": 1.3, "实验室老师": 1.2},
    "teacher_count":   {},
    "counselor_count": {"辅导员": 1.5},
    "admin_count":     {},
    "dorm_staff_count": {"宿管人员": 2.0},
    "security_count":  {"保卫处人员": 2.0},
    "canteen_staff_count": {"食堂工作人员": 1.8, "食堂管理人员": 1.5},
    "clinic_staff_count": {"校医院人员": 1.8},
}


def _clamp_ratio(x: float) -> float:
    return max(0.0, min(1.0, x))


def compute_calibrated_proportions(
    scale: str,
    calibration: Dict[str, Any],
    base_demographics: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    根据本校校准数据，返回：
    - proportions : 各 archetype 校准后的占比
    - field_status: 每个校准字段的『用户填写 / 系统估计』状态
    - credibility : 数据可信度（low / medium / high）
    - source_breakdown: 数据来源说明
    - warnings: 系统对缺失字段的标注
    """
    if scale not in SCHOOL_SCALES:
        scale = "普通本科高校"
    base = base_demographics if base_demographics is not None else get_demographics(scale)
    props = {row["archetype"]: row["proportion"] for row in base}

    field_status: Dict[str, str] = {}
    filled = 0
    total_numeric = 0
    for f in CALIBRATION_FIELDS:
        key = f["key"]
        if key == "school_scale":
            continue
        if f["type"] in ("number", "ratio"):
            total_numeric += 1
        if calibration.get(key) is None:
            field_status[key] = "系统估计值"
        else:
            field_status[key] = "用户填写"
            if f["type"] in ("number", "ratio"):
                filled += 1

    # 应用校准缩放
    for field_key, scalars in ARCHETYPE_FIELD_SCALARS.items():
        val = calibration.get(field_key)
        if val is None:
            continue
        if field_key.endswith("_ratio"):
            # 比例字段 val ∈ [0,1]，越接近 1 越放大
            scale_factor = 0.5 + 1.5 * _clamp_ratio(float(val))
        else:
            # 数量字段：用『是否有填写』表示
            scale_factor = 1.5 if float(val) > 0 else 1.0
        for arch, s in scalars.items():
            if arch in props:
                props[arch] *= (s * scale_factor)

    # 重新归一化
    total = sum(props.values()) or 1.0
    proportions = {k: v / total for k, v in props.items()}

    # 可信度
    if total_numeric == 0 or filled == 0:
        credibility = "low"
    elif filled >= total_numeric * 0.5:
        credibility = "high"
    else:
        credibility = "medium"

    warnings: List[str] = []
    for f in CALIBRATION_FIELDS:
        if f["key"] == "school_scale":
            continue
        if calibration.get(f["key"]) is None:
            warnings.append(f"「{f['label']}」为系统估计值，建议后续用本校数据校准")

    # 数据来源说明
    source_breakdown = {
        "用户输入": [k for k, v in field_status.items() if v == "用户填写"],
        "默认模型": [k for k, v in field_status.items() if v == "系统估计值"],
        "问卷结果": "问卷数据由前端采集 / 模拟",
        "公开数据": "发布内容、规则类别映射（来自 knowledge 知识库）",
    }

    return {
        "scale": scale,
        "proportions": {k: round(v, 4) for k, v in proportions.items()},
        "field_status": field_status,
        "credibility": credibility,
        "filled_count": filled,
        "total_numeric_fields": total_numeric,
        "warnings": warnings,
        "source_breakdown": source_breakdown,
    }


def list_calibration_fields() -> List[Dict[str, Any]]:
    return CALIBRATION_FIELDS


def compare_with_default(scale: str, calibration: Dict[str, Any]) -> Dict[str, Any]:
    """
    返回校准前后对比：哪些 archetype 的占比上升 / 下降。
    """
    default = get_demographics(scale)
    calibrated = compute_calibrated_proportions(scale, calibration, base_demographics=default)

    default_p = {row["archetype"]: row["proportion"] for row in default}
    cal_p = calibrated["proportions"]

    diffs: List[Dict[str, Any]] = []
    for arch in default_p:
        d = default_p[arch]
        c = cal_p.get(arch, d)
        delta = c - d
        if abs(delta) > 0.001:
            diffs.append({
                "archetype": arch,
                "category": _category_by_archetype(arch),
                "default": round(d, 4),
                "calibrated": round(c, 4),
                "delta": round(delta, 4),
                "direction": "up" if delta > 0 else "down",
            })
    diffs.sort(key=lambda x: abs(x["delta"]), reverse=True)
    return {
        "scale": scale,
        "credibility": calibrated["credibility"],
        "diffs": diffs,
        "filled_count": calibrated["filled_count"],
        "total_numeric_fields": calibrated["total_numeric_fields"],
    }
