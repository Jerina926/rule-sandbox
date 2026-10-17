# -*- coding: utf-8 -*-
"""
虚拟校园人物关系网络
====================

把虚拟人物当成"有关系"的社会节点，而不是孤立个体。

数据结构：
- Node  : {id, name, archetype, category}    一个人物
- Edge  : {source, target, relation, weight, direction}
   direction 可为 `forward` / `bidirectional` / `feedback`
- Chain : 一条有序链条 [{node, transition}]，可被人读懂

本模块提供 3 类关系：
1. **直接影响**：A 的行为直接 → B 的场景压力
   经常晚归学生 → 宿管人员（登记压力上升）
2. **传导影响**：A → B → C 多跳链条
   作息规律学生 → 辅导员（投诉） → 学生处（汇报）
3. **舆论/放大**：少数高影响力角色把局部事件扩散
   学生干部 → 班级群 → 全年级

每一个关系都有 triggers（命中规则类别）与 description（人话解释），
避免出现医保/电商/优惠券等非学校场景关键词。
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Tuple, Optional


# ---------------------------------------------------------------------------
# 节点：与 persona_library 对齐
# ---------------------------------------------------------------------------

@dataclass
class PersonaNode:
    id: str
    name: str
    archetype: str
    category: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# 边：A → B（方向 + 影响类型 + 强度）
# ---------------------------------------------------------------------------

@dataclass
class PersonaEdge:
    source: str
    target: str
    relation: str           # 人话描述，例如『登记者压力』『投诉通道』『舆情扩散』
    direction: str         # forward / bidirectional / feedback
    weight: float          # 0~1，影响强度
    triggers: List[str] = field(default_factory=list)   # 命中的发布内容词
    description: str = ""  # 人话解释

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# 25+ 关系定义（全部为校园场景；含 strong forward 链条 + 反馈环路）
# ---------------------------------------------------------------------------

EDGES: List[PersonaEdge] = [
    # ---- 直接影响：晚归/作息/安全 ----
    PersonaEdge(
        source="stu_often_late", target="mgr_dorm",
        relation="登记压力 ↑", direction="forward", weight=0.85,
        triggers=["宵禁", "晚归", "门禁", "宿舍"],
        description="经常晚归学生增加夜间外出 → 宿管人员登记与巡查工作量上升",
    ),
    PersonaEdge(
        source="stu_often_late", target="mgr_security",
        relation="夜间巡查压力 ↑", direction="forward", weight=0.75,
        triggers=["宵禁", "晚归", "门禁", "夜间"],
        description="晚归学生增加夜间出入频率 → 保卫处巡逻与应急响应压力上升",
    ),
    PersonaEdge(
        source="stu_regular", target="mgr_counselor",
        relation="投诉通道", direction="forward", weight=0.70,
        triggers=["宵禁", "晚归", "作息", "噪音", "宿舍"],
        description="作息规律学生若被噪音影响 → 向辅导员发起投诉或联合签名",
    ),
    PersonaEdge(
        source="stu_regular", target="mgr_dorm",
        relation="反映诉求", direction="forward", weight=0.55,
        triggers=["宵禁", "宿舍", "作息", "门禁"],
        description="作息规律学生会向宿管反映夜间噪音问题，要求恢复管理",
    ),
    PersonaEdge(
        source="stu_club", target="mgr_counselor",
        relation="活动反馈", direction="forward", weight=0.45,
        triggers=["社团", "活动", "门禁", "宵禁"],
        description="社团活跃学生因活动晚归时，会主动与辅导员沟通替代方案",
    ),
    PersonaEdge(
        source="stu_intern", target="mgr_counselor",
        relation="实习请假冲突", direction="forward", weight=0.55,
        triggers=["实习", "晚归", "门禁"],
        description="实习学生请假与晚归登记存在流程冲突，会向辅导员反馈",
    ),
    PersonaEdge(
        source="stu_grad_entrance", target="mgr_library",
        relation="自习空间依赖", direction="forward", weight=0.60,
        triggers=["图书馆", "自习", "门禁", "宵禁"],
        description="考研学生深度依赖图书馆延长开放 → 与图书馆夜间管理联动",
    ),
    PersonaEdge(
        source="mgr_counselor", target="mgr_student_affairs",
        relation="信息上报", direction="forward", weight=0.65,
        triggers=["宿舍", "学生管理", "舆情"],
        description="辅导员汇集学生反馈 → 统一上报学生处，影响学校层面决策",
    ),
    PersonaEdge(
        source="mgr_dorm", target="mgr_student_affairs",
        relation="执行反馈", direction="forward", weight=0.70,
        triggers=["宿舍", "门禁", "晚归"],
        description="宿管人员向学生处反馈一线执行压力，要求明确替代管理方案",
    ),
    PersonaEdge(
        source="mgr_security", target="mgr_student_affairs",
        relation="夜间异常上报", direction="forward", weight=0.60,
        triggers=["安全", "夜归", "门禁"],
        description="保卫处对夜间异常事件统一上报学生处 / 主管校领导",
    ),
    PersonaEdge(
        source="mgr_student_affairs", target="mgr_secretary",
        relation="决策建议", direction="forward", weight=0.75,
        triggers=["学生管理", "宿舍", "舆情"],
        description="学生处汇集一线信息 → 提交学院书记 / 校领导决策",
    ),
    # ---- 舆论/放大链路 ----
    PersonaEdge(
        source="stu_cadre", target="stu_dorm",
        relation="班级群扩散", direction="forward", weight=0.55,
        triggers=["宿舍", "门禁", "活动", "舆情"],
        description="学生干部通过班级群扩散对规则的解读，影响其他学生态度",
    ),
    PersonaEdge(
        source="stu_cadre", target="mgr_counselor",
        relation="诉求通道", direction="bidirectional", weight=0.60,
        triggers=["学生", "宿舍", "舆情"],
        description="学生干部既向辅导员传递学生诉求，也带回学校解释",
    ),
    PersonaEdge(
        source="stu_club", target="stu_dorm",
        relation="同伴影响", direction="forward", weight=0.40,
        triggers=["社团", "门禁", "活动"],
        description="社团活跃学生的『夜归自由』会带动普通住校生心理预期",
    ),
    PersonaEdge(
        source="stu_cadre", target="stu_club",
        relation="协调桥梁", direction="forward", weight=0.35,
        triggers=["活动", "门禁"],
        description="学生干部与社团活跃学生互动后，会在班级层面协调活动",
    ),
    PersonaEdge(
        source="ext_parent", target="mgr_counselor",
        relation="电话质询", direction="forward", weight=0.55,
        triggers=["安全", "晚归", "宿舍", "门禁"],
        description="家长通过电话/微信直接质询辅导员，要求保障孩子安全",
    ),
    PersonaEdge(
        source="ext_parent", target="mgr_secretary",
        relation="舆情压力", direction="forward", weight=0.50,
        triggers=["安全", "舆情"],
        description="家长群体通过 12345 / 媒体表达担忧，形成外部舆情压力",
    ),
    PersonaEdge(
        source="ext_community", target="mgr_student_affairs",
        relation="周边反馈", direction="forward", weight=0.30,
        triggers=["夜间", "宿舍", "周边"],
        description="周边社区居民若发现夜间异常，会向学校学生处反馈",
    ),
    PersonaEdge(
        source="stu_low_income", target="stu_cadre",
        relation="信息获取", direction="forward", weight=0.45,
        triggers=["奖助", "信息"],
        description="贫困生偏好通过学生干部 / 班级群获取奖助学金与勤工俭学信息",
    ),
    PersonaEdge(
        source="stu_intl", target="mgr_student_affairs",
        relation="跨文化沟通", direction="forward", weight=0.40,
        triggers=["留学生", "文化"],
        description="留学生会通过留学生办公室 → 学生处反馈住宿/门禁意见",
    ),
    # ---- 反馈环路：A→B→A 或 B 倒逼 A ----
    PersonaEdge(
        source="mgr_student_affairs", target="stu_dorm",
        relation="规则颁布", direction="forward", weight=0.80,
        triggers=["宿舍", "门禁", "宵禁"],
        description="学生处根据调研结果颁布/调整宿舍管理规则",
    ),
    PersonaEdge(
        source="mgr_counselor", target="stu_dorm",
        relation="解释说明", direction="forward", weight=0.50,
        triggers=["宿舍", "舆情", "门禁"],
        description="辅导员在班级群/班会上解释规则的调整，缓解学生焦虑",
    ),
    PersonaEdge(
        source="mgr_dorm", target="stu_regular",
        relation="秩序恢复", direction="bidirectional", weight=0.40,
        triggers=["宿舍", "门禁", "作息"],
        description="宿管人员根据作息规律学生诉求，恢复秩序或调整制度",
    ),
    PersonaEdge(
        source="mgr_clinic", target="mgr_student_affairs",
        relation="急诊压力上报", direction="forward", weight=0.50,
        triggers=["安全", "夜间", "应急"],
        description="校医院登记夜间急诊压力，反推夜间安全管理",
    ),
    PersonaEdge(
        source="tch_head", target="mgr_counselor",
        relation="班主任-辅导员联动", direction="bidirectional", weight=0.55,
        triggers=["宿舍", "学生管理", "班主任"],
        description="班主任与辅导员互通班级情况，共同处理学生问题",
    ),
    PersonaEdge(
        source="stu_risk_fail", target="mgr_counselor",
        relation="预警信号", direction="forward", weight=0.60,
        triggers=["学业", "心理", "宿舍"],
        description="挂科风险学生的异常行为是辅导员预警信号",
    ),
    PersonaEdge(
        source="stu_parttime", target="mgr_dorm",
        relation="晚归合规化", direction="bidirectional", weight=0.40,
        triggers=["兼职", "晚归", "门禁"],
        description="兼职学生晚归通过宿管登记，避免被误判为问题学生",
    ),
    PersonaEdge(
        source="mgr_library", target="stu_grad_entrance",
        relation="自习延长", direction="bidirectional", weight=0.50,
        triggers=["图书馆", "自习", "门禁"],
        description="考研学生诉求推动图书馆延长开放时间，开放后支撑更多学生",
    ),
    PersonaEdge(
        source="mgr_canteen", target="stu_often_late",
        relation="夜间供餐需求", direction="forward", weight=0.35,
        triggers=["食堂", "晚归"],
        description="晚归学生增加可能带动食堂夜间窗口需求",
    ),
    PersonaEdge(
        source="mgr_secretary", target="mgr_student_affairs",
        relation="决策指示", direction="feedback", weight=0.80,
        triggers=["学生管理", "舆情", "宿舍"],
        description="学院书记 / 校领导根据学生处材料下达调整决策",
    ),
]


# ---------------------------------------------------------------------------
# 链条：人话版风险链（5+ 条 chain）
# ---------------------------------------------------------------------------

CHAIN_TEMPLATES: List[Dict[str, Any]] = [
    {
        "key": "宵禁取消_主线",
        "title": "规则生效主线（宵禁取消）",
        "triggers": ["宵禁", "晚归", "门禁"],
        "path": [
            "学校发布取消宵禁",
            "经常晚归学生：增加夜间外出频率",
            "宿管人员：登记与巡查工作量急剧上升",
            "作息规律学生：夜间噪音影响 → 投诉",
            "辅导员：协调两类学生并上报情况",
            "学生处：收到执行反馈，启动应急调整",
            "学校：可能收紧规则或延长图书馆开放",
        ],
        "risk_level": "medium",
        "description": "这是『取消宵禁』的主传导链路：高频晚归人群扩大压力，秩序维护链条反向收紧",
    },
    {
        "key": "图书馆延时_主线",
        "title": "图书馆延时主线",
        "triggers": ["图书馆", "自习", "门禁"],
        "path": [
            "学校延长图书馆开放时间",
            "考研学生：自习时间增加 → 校内停留更久",
            "图书馆管理员：夜间管理压力上升",
            "宿舍人员：夜间回家需求减弱",
            "辅导员：部分学生反馈宿舍作息被影响",
            "学校：评估深夜通勤与宿舍规则联动",
        ],
        "risk_level": "low",
        "description": "图书馆延时与宿舍规则之间存在联动；可能导致宿舍需求下降或作息冲突",
    },
    {
        "key": "食堂涨价_主线",
        "title": "食堂涨价主线",
        "triggers": ["食堂", "涨价", "价格", "餐饮"],
        "path": [
            "学校调整食堂价格",
            "贫困学生：助学金/兼职需求突增",
            "食堂工作人员：营业额波动 → 排班调整",
            "家长：经济压力质询",
            "学生干部：班级群转发意见",
            "辅导员：汇总上报学生处",
            "学校：评估补贴/价格联动调整",
        ],
        "risk_level": "medium",
        "description": "价格调整直接冲击经济敏感群体，并通过班级群/家长扩大舆情",
    },
    {
        "key": "综测加分_主线",
        "title": "综测志愿加分主线",
        "triggers": ["综测", "志愿", "加分", "学生干部"],
        "path": [
            "学校综测新增志愿加分",
            "学生干部：参与志愿以争取加分",
            "社团活跃学生：组织志愿活动",
            "辅导员：审核志愿时长真实性",
            "学生处：抽查与争议处理",
            "普通学生：质疑公平性 → 投诉",
            "学校：调整加分细则或加强审核",
        ],
        "risk_level": "medium",
        "description": "加分政策传导：激励干部/社团群体，但引发公平性争议",
    },
    {
        "key": "网络舆情_主线",
        "title": "舆情扩散环路",
        "triggers": ["宿舍", "门禁", "舆情", "安全"],
        "path": [
            "事件触发（夜归冲突/规则争议）",
            "学生干部 / 社团学生：在班级群扩散",
            "校外平台：小红书/微博出现话题",
            "家长：通过 12345/媒体表达担忧",
            "外部校友/媒体关注",
            "学校：被动进入应急处置流程",
        ],
        "risk_level": "high",
        "description": "从校内群扩散到校外舆情，进入被动应急",
    },
    {
        "key": "安全应急_主线",
        "title": "夜间安全应急环路",
        "triggers": ["安全", "夜间", "应急", "宿舍"],
        "path": [
            "取消宵禁后夜间出入增多",
            "保卫处：巡逻频次上升但人手有限",
            "校医院：急诊压力同步上升",
            "突发事件：夜间意外/冲突",
            "辅导员/保卫处：应急响应与上报",
            "学生处：协调处理并发布通报",
            "学校：评估是否恢复/调整规则",
        ],
        "risk_level": "high",
        "description": "夜间安全事件链；任何一环响应不及时都可能升级",
    },
]


# ---------------------------------------------------------------------------
# 查询接口
# ---------------------------------------------------------------------------

def _norm(text: str) -> str:
    import re
    return re.sub(r"\s+", "", text or "")


def _hits(text: str, triggers: List[str]) -> int:
    return sum(1 for t in triggers if _norm(t) in text)


def list_edges() -> List[Dict[str, Any]]:
    return [e.to_dict() for e in EDGES]


def list_chain_templates() -> List[Dict[str, Any]]:
    return CHAIN_TEMPLATES


def match_edges(content: str, category_hint: str = "") -> List[Dict[str, Any]]:
    """
    根据发布内容，过滤出与当前规则相关的边。
    返回按 weight 排序的边列表。
    """
    matched: List[Dict[str, Any]] = []
    text = _norm(content)
    for e in EDGES:
        score = _hits(text, e.triggers)
        if score >= 1:
            d = e.to_dict()
            d["match_score"] = float(score)
            matched.append(d)
    matched.sort(key=lambda x: (x["match_score"], x["weight"]), reverse=True)
    return matched


def match_chains(content: str, category_hint: str = "") -> List[Dict[str, Any]]:
    """
    根据发布内容，匹配出关联的链条。返回模板的副本（避免共享）。
    """
    text = _norm(content)
    matched: List[Dict[str, Any]] = []
    for ch in CHAIN_TEMPLATES:
        score = _hits(text, ch["triggers"])
        if score >= 1:
            d = dict(ch)
            d["match_score"] = float(score)
            matched.append(d)
    matched.sort(key=lambda x: x["match_score"], reverse=True)
    return matched


def network_for_content(content: str, category_hint: str = "") -> Dict[str, Any]:
    """
    端到端：根据发布内容，返回节点+边+链条 的可可视化网络结构。
    """
    edges = match_edges(content, category_hint)
    chains = match_chains(content, category_hint)

    # 抽取命中的节点 id
    node_ids = set()
    for e in edges:
        node_ids.add(e["source"])
        node_ids.add(e["target"])

    # 节点详细信息（从 persona_library 反查，避免循环导入，使用懒导入）
    from .persona_library import PERSONA_BY_ID
    nodes: List[Dict[str, Any]] = []
    for nid in node_ids:
        p = PERSONA_BY_ID.get(nid)
        if not p:
            continue
        nodes.append({
            "id": p.id,
            "name": p.name,
            "archetype": p.archetype,
            "category": p.category,
            "attitude": p.attitude,
            "stance_label": p.stance_label,
            "influence": p.influence,
            "risk_tilt": p.risk_tilt,
        })

    return {
        "content": content,
        "category_hint": category_hint,
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "total_chains": len(chains),
        "nodes": nodes,
        "edges": edges,
        "chains": chains,
        "disclaimer": "所有人物、关系、链条均为虚拟校园仿真参数，仅用于推演，不代表真实情况。",
    }
