# -*- coding: utf-8 -*-
"""
人口结构比例与权重模型
======================

本模块提供 5 种学校规模（小型学院 / 普通本科 / 综合性大学 / 住宿制高校 / 职业院校）
的人口结构默认比例、关注度、对当前规则的态度、支持度/风险/执行权重等参数。

字段（每类人群）：
- id          : 人群 id（与 persona_library 中 archetype 对齐）
- category    : 所属大类
- archetype   : 人物类型
- proportion  : 在该学校规模下的人群占比（0~1）
- focus       : 对当前规则的关注度（0~1）
- attitude    : 对当前规则的态度倾向（-100~+100），与 persona_library 默认值一致
- weight_support : 对总体支持度的权重（0~1）
- weight_risk    : 对风险指数的权重（0~1）
- weight_execution : 对执行难度的权重（0~1）
- influence      : 影响力等级（1~4）
- representative : 典型代表人物 id（指向 persona_library）

说明：
- 比例符合一般高校常识（学生远多于教师 / 管理 / 服务）
- 占比仅用于模拟推演，不代表真实学校数据
- 用户可在前端『人口结构设置』区域手动调整
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Tuple

from .persona_library import ALL_PERSONAS, Persona, PERSONA_BY_ID


# ---------------------------------------------------------------------------
# 学校规模
# ---------------------------------------------------------------------------

SCHOOL_SCALES = [
    "小型学院",
    "普通本科高校",
    "综合性大学",
    "住宿制高校",
    "职业院校",
]


SCALE_DESCRIPTIONS = {
    "小型学院":     "在校生 5,000 人以下；师资与管理高度集中；辅导员比 1:200 以上",
    "普通本科高校": "在校生 10,000~25,000 人；教学与生活配套齐全；学生住校比中等",
    "综合性大学":   "在校生 30,000 人以上；多校区/多学科；学生群体高度多元",
    "住宿制高校":   "在校生 8,000~15,000 人；住校比例 > 90%；管理与服务高度集中",
    "职业院校":     "在校生 6,000~12,000 人；实践教学占比高；学生住校比高、晚归频率较高",
}


# ---------------------------------------------------------------------------
# 5 种规模 × 每种 archetype 的参数
# ---------------------------------------------------------------------------

# 默认共享参数：每个 archetype 在不同规模下的（关注度、权重、代表性）
# 数值由本模块静态配置 + persona_library 默认 attitude 提供

ARCHETYPE_BASE = {
    # ---- 学生群体 ----
    "大一新生":          dict(focus=0.55, w_s=1.0, w_r=0.4, w_e=0.2, influence=1),
    "普通住校生":        dict(focus=0.92, w_s=1.8, w_r=0.6, w_e=0.5, influence=2),
    "走读生":            dict(focus=0.30, w_s=0.6, w_r=0.2, w_e=0.1, influence=1),
    "毕业生":            dict(focus=0.65, w_s=1.0, w_r=0.3, w_e=0.3, influence=2),
    "考研学生":          dict(focus=0.78, w_s=1.2, w_r=0.3, w_e=0.3, influence=2),
    "学生干部":          dict(focus=0.70, w_s=1.3, w_r=0.6, w_e=0.5, influence=3),
    "社团活跃学生":      dict(focus=0.72, w_s=1.0, w_r=0.5, w_e=0.4, influence=2),
    "挂科风险学生":      dict(focus=0.45, w_s=0.4, w_r=1.0, w_e=0.3, influence=1),
    "贫困生":            dict(focus=0.40, w_s=0.6, w_r=0.4, w_e=0.2, influence=1),
    "留学生":            dict(focus=0.35, w_s=0.5, w_r=0.2, w_e=0.2, influence=1),
    "经常晚归学生":      dict(focus=0.85, w_s=1.4, w_r=2.5, w_e=0.8, influence=2),
    "作息规律学生":      dict(focus=0.80, w_s=1.6, w_r=0.7, w_e=0.5, influence=2),
    "实习学生":          dict(focus=0.75, w_s=1.2, w_r=0.4, w_e=0.4, influence=2),
    "兼职学生":          dict(focus=0.55, w_s=0.8, w_r=0.5, w_e=0.3, influence=1),
    # ---- 教师群体 ----
    "公共课教师":        dict(focus=0.30, w_s=0.5, w_r=0.2, w_e=0.1, influence=2),
    "专业课教师":        dict(focus=0.45, w_s=0.7, w_r=0.3, w_e=0.2, influence=2),
    "班主任":            dict(focus=0.75, w_s=1.2, w_r=1.0, w_e=1.0, influence=3),
    "导师":              dict(focus=0.55, w_s=0.9, w_r=0.4, w_e=0.4, influence=2),
    "实验室老师":        dict(focus=0.30, w_s=0.4, w_r=0.3, w_e=0.2, influence=2),
    "行政兼课教师":      dict(focus=0.20, w_s=0.3, w_r=0.2, w_e=0.2, influence=2),
    # ---- 管理人员 ----
    "辅导员":            dict(focus=0.85, w_s=1.4, w_r=1.2, w_e=2.0, influence=3),
    "学院书记":          dict(focus=0.70, w_s=1.2, w_r=1.0, w_e=1.0, influence=4),
    "教务处老师":        dict(focus=0.30, w_s=0.4, w_r=0.3, w_e=0.3, influence=2),
    "学生处老师":        dict(focus=0.75, w_s=1.0, w_r=1.0, w_e=1.0, influence=4),
    "宿管人员":          dict(focus=0.95, w_s=1.6, w_r=0.8, w_e=3.0, influence=2),
    "保卫处人员":        dict(focus=0.80, w_s=1.0, w_r=1.5, w_e=2.5, influence=3),
    "图书馆管理员":      dict(focus=0.55, w_s=0.7, w_r=0.3, w_e=0.4, influence=2),
    "食堂管理人员":      dict(focus=0.45, w_s=0.5, w_r=0.3, w_e=0.5, influence=2),
    "校医院人员":        dict(focus=0.50, w_s=0.4, w_r=0.8, w_e=0.6, influence=2),
    # ---- 校园服务人员 ----
    "食堂工作人员":      dict(focus=0.20, w_s=0.2, w_r=0.2, w_e=0.3, influence=1),
    "保洁人员":          dict(focus=0.15, w_s=0.1, w_r=0.1, w_e=0.3, influence=1),
    "维修人员":          dict(focus=0.20, w_s=0.1, w_r=0.2, w_e=0.3, influence=1),
    "快递站人员":        dict(focus=0.10, w_s=0.1, w_r=0.1, w_e=0.1, influence=1),
    "超市工作人员":      dict(focus=0.10, w_s=0.1, w_r=0.1, w_e=0.1, influence=1),
    # ---- 外部相关者 ----
    "家长":              dict(focus=0.70, w_s=0.9, w_r=1.0, w_e=0.6, influence=3),
    "校友":              dict(focus=0.30, w_s=0.4, w_r=0.2, w_e=0.2, influence=2),
    "实习单位":          dict(focus=0.40, w_s=0.5, w_r=0.2, w_e=0.2, influence=2),
    "周边商家":          dict(focus=0.25, w_s=0.2, w_r=0.2, w_e=0.2, influence=1),
    "社区居民":          dict(focus=0.25, w_s=0.2, w_r=0.3, w_e=0.2, influence=1),
}


# 各规模下 archetype 的占比（每行 sum=1）
# 原则：学生占大头；不同规模仅调整细分配比
SCALE_PROPORTION: Dict[str, Dict[str, float]] = {
    "小型学院": {
        # 学生合计约 0.86
        "大一新生": 0.16, "普通住校生": 0.30, "走读生": 0.04,
        "毕业生": 0.06, "考研学生": 0.06, "学生干部": 0.04,
        "社团活跃学生": 0.04, "挂科风险学生": 0.04, "贫困生": 0.04,
        "留学生": 0.01, "经常晚归学生": 0.02, "作息规律学生": 0.04,
        "实习学生": 0.01, "兼职学生": 0.04,
        # 教师合计约 0.06
        "公共课教师": 0.018, "专业课教师": 0.022, "班主任": 0.005,
        "导师": 0.005, "实验室老师": 0.005, "行政兼课教师": 0.005,
        # 管理 0.04
        "辅导员": 0.012, "学院书记": 0.002, "教务处老师": 0.003,
        "学生处老师": 0.002, "宿管人员": 0.008, "保卫处人员": 0.005,
        "图书馆管理员": 0.003, "食堂管理人员": 0.002, "校医院人员": 0.003,
        # 服务 0.02
        "食堂工作人员": 0.006, "保洁人员": 0.005, "维修人员": 0.003,
        "快递站人员": 0.002, "超市工作人员": 0.004,
        # 外部 0.02
        "家长": 0.012, "校友": 0.003, "实习单位": 0.002,
        "周边商家": 0.002, "社区居民": 0.001,
    },
    "普通本科高校": {
        # 学生合计约 0.84
        "大一新生": 0.13, "普通住校生": 0.27, "走读生": 0.06,
        "毕业生": 0.08, "考研学生": 0.08, "学生干部": 0.04,
        "社团活跃学生": 0.05, "挂科风险学生": 0.04, "贫困生": 0.04,
        "留学生": 0.02, "经常晚归学生": 0.02, "作息规律学生": 0.04,
        "实习学生": 0.03, "兼职学生": 0.04,
        # 教师 0.07
        "公共课教师": 0.020, "专业课教师": 0.026, "班主任": 0.006,
        "导师": 0.008, "实验室老师": 0.005, "行政兼课教师": 0.005,
        # 管理 0.04
        "辅导员": 0.012, "学院书记": 0.002, "教务处老师": 0.003,
        "学生处老师": 0.002, "宿管人员": 0.010, "保卫处人员": 0.005,
        "图书馆管理员": 0.003, "食堂管理人员": 0.002, "校医院人员": 0.003,
        # 服务 0.02
        "食堂工作人员": 0.006, "保洁人员": 0.005, "维修人员": 0.003,
        "快递站人员": 0.002, "超市工作人员": 0.004,
        # 外部 0.03
        "家长": 0.020, "校友": 0.004, "实习单位": 0.003,
        "周边商家": 0.002, "社区居民": 0.001,
    },
    "综合性大学": {
        # 学生合计约 0.81（多元化）
        "大一新生": 0.11, "普通住校生": 0.22, "走读生": 0.10,
        "毕业生": 0.09, "考研学生": 0.10, "学生干部": 0.04,
        "社团活跃学生": 0.05, "挂科风险学生": 0.03, "贫困生": 0.03,
        "留学生": 0.04, "经常晚归学生": 0.02, "作息规律学生": 0.03,
        "实习学生": 0.04, "兼职学生": 0.03,
        # 教师 0.08
        "公共课教师": 0.022, "专业课教师": 0.030, "班主任": 0.006,
        "导师": 0.012, "实验室老师": 0.005, "行政兼课教师": 0.005,
        # 管理 0.05
        "辅导员": 0.014, "学院书记": 0.003, "教务处老师": 0.004,
        "学生处老师": 0.003, "宿管人员": 0.010, "保卫处人员": 0.006,
        "图书馆管理员": 0.004, "食堂管理人员": 0.003, "校医院人员": 0.003,
        # 服务 0.02
        "食堂工作人员": 0.006, "保洁人员": 0.005, "维修人员": 0.003,
        "快递站人员": 0.002, "超市工作人员": 0.004,
        # 外部 0.04
        "家长": 0.025, "校友": 0.006, "实习单位": 0.004,
        "周边商家": 0.003, "社区居民": 0.002,
    },
    "住宿制高校": {
        # 学生合计约 0.86（高住校）
        "大一新生": 0.14, "普通住校生": 0.40, "走读生": 0.01,
        "毕业生": 0.05, "考研学生": 0.07, "学生干部": 0.04,
        "社团活跃学生": 0.04, "挂科风险学生": 0.04, "贫困生": 0.04,
        "留学生": 0.01, "经常晚归学生": 0.03, "作息规律学生": 0.03,
        "实习学生": 0.01, "兼职学生": 0.03,
        # 教师 0.06
        "公共课教师": 0.020, "专业课教师": 0.020, "班主任": 0.005,
        "导师": 0.005, "实验室老师": 0.005, "行政兼课教师": 0.005,
        # 管理 0.04
        "辅导员": 0.012, "学院书记": 0.002, "教务处老师": 0.002,
        "学生处老师": 0.002, "宿管人员": 0.014, "保卫处人员": 0.006,
        "图书馆管理员": 0.003, "食堂管理人员": 0.002, "校医院人员": 0.003,
        # 服务 0.02
        "食堂工作人员": 0.007, "保洁人员": 0.005, "维修人员": 0.003,
        "快递站人员": 0.002, "超市工作人员": 0.003,
        # 外部 0.02
        "家长": 0.014, "校友": 0.002, "实习单位": 0.002,
        "周边商家": 0.001, "社区居民": 0.001,
    },
    "职业院校": {
        # 学生合计约 0.85（晚归率高）
        "大一新生": 0.16, "普通住校生": 0.32, "走读生": 0.03,
        "毕业生": 0.05, "考研学生": 0.01, "学生干部": 0.04,
        "社团活跃学生": 0.05, "挂科风险学生": 0.05, "贫困生": 0.05,
        "留学生": 0.005, "经常晚归学生": 0.05, "作息规律学生": 0.02,
        "实习学生": 0.06, "兼职学生": 0.05,
        # 教师 0.06
        "公共课教师": 0.018, "专业课教师": 0.022, "班主任": 0.005,
        "导师": 0.002, "实验室老师": 0.010, "行政兼课教师": 0.005,
        # 管理 0.04
        "辅导员": 0.012, "学院书记": 0.002, "教务处老师": 0.002,
        "学生处老师": 0.002, "宿管人员": 0.010, "保卫处人员": 0.005,
        "图书馆管理员": 0.003, "食堂管理人员": 0.002, "校医院人员": 0.003,
        # 服务 0.02
        "食堂工作人员": 0.007, "保洁人员": 0.005, "维修人员": 0.003,
        "快递站人员": 0.002, "超市工作人员": 0.003,
        # 外部 0.03
        "家长": 0.020, "校友": 0.003, "实习单位": 0.004,
        "周边商家": 0.002, "社区居民": 0.001,
    },
}


def _archetype_by_persona_id(pid: str) -> str:
    for p in ALL_PERSONAS:
        if p.id == pid:
            return p.archetype
    return ""


def _attitude_by_archetype(archetype: str) -> int:
    for p in ALL_PERSONAS:
        if p.archetype == archetype:
            return p.attitude
    return 0


def _category_by_archetype(archetype: str) -> str:
    for p in ALL_PERSONAS:
        if p.archetype == archetype:
            return p.category
    return ""


def _influence_by_archetype(archetype: str) -> int:
    base = ARCHETYPE_BASE.get(archetype, {})
    return base.get("influence", 1)


def list_scales() -> List[Dict[str, str]]:
    return [{"scale": s, "description": SCALE_DESCRIPTIONS.get(s, "")} for s in SCHOOL_SCALES]


def get_demographics(scale: str, overrides: Dict[str, float] = None) -> List[Dict[str, Any]]:
    """
    返回某规模下全部 archetype 的比例/权重/态度。
    overrides 为可选手动覆盖（key=archetype, value=proportion 0~1）。
    """
    if scale not in SCHOOL_SCALES:
        scale = "普通本科高校"
    prop = dict(SCALE_PROPORTION[scale])
    if overrides:
        for k, v in overrides.items():
            if k in prop and v is not None:
                prop[k] = max(0.0, min(1.0, float(v)))
    # 重新归一化（sum=1）
    total = sum(prop.values()) or 1.0
    prop = {k: v / total for k, v in prop.items()}

    out: List[Dict[str, Any]] = []
    for arch, p in prop.items():
        base = ARCHETYPE_BASE.get(arch, {})
        out.append({
            "archetype": arch,
            "category": _category_by_archetype(arch),
            "proportion": round(p, 4),
            "focus": base.get("focus", 0.5),
            "attitude": _attitude_by_archetype(arch),
            "weight_support": base.get("w_s", 1.0),
            "weight_risk": base.get("w_r", 0.5),
            "weight_execution": base.get("w_e", 0.5),
            "influence": base.get("influence", 1),
            "representative": _first_persona_by_archetype(arch),
        })
    return out


def _first_persona_by_archetype(archetype: str) -> str:
    for p in ALL_PERSONAS:
        if p.archetype == archetype:
            return p.id
    return ""


def category_totals(scale: str) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for arch, p in SCALE_PROPORTION.get(scale, {}).items():
        cat = _category_by_archetype(arch)
        out[cat] = out.get(cat, 0.0) + p
    return out
