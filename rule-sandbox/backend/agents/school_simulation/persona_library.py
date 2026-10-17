# -*- coding: utf-8 -*-
"""
虚拟学校人物画像库
==================

本模块提供「虚拟学校人口画像库」的完整数据。所有人物均为虚构原型，
用于覆盖学校内部主要人群类型，不涉及任何真实个人信息。

字段说明（每人物）：
- id            : 唯一标识
- name          : 虚拟姓名
- archetype     : 人物类型（原型）
- category      : 所属大类（学生/教师/管理/服务/外部）
- grade_or_role : 年级或岗位
- behavior      : 日常行为特征
- demands       : 核心诉求
- sensitivities : 敏感问题
- attitude      : 对当前规则的态度倾向（-100~+100）
- stance_label  : 态度标签（强烈支持/支持/中立/反对/强烈反对）
- reason        : 支持或反对原因
- likely_actions: 可能采取的行为
- influence     : 影响力等级（1=普通个体 / 2=小群体代表 / 3=组织或舆论代表 / 4=决策相关方）
- risk_tilt     : 风险倾向（0=无 / 1=低 / 2=中 / 3=高 / 4=极高）
- judgment_basis: 系统判断依据
- triggers      : 触发关注该人物的发布内容关键词

本库为「数据驱动 + 关键词匹配」混合模式：
- triggers 用于判断该人物是否与当前发布内容「强相关」
- attitude / risk_tilt / influence 进入后续人口比例与双源融合计算
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Tuple


@dataclass
class Persona:
    id: str
    name: str
    archetype: str
    category: str
    grade_or_role: str
    behavior: str
    demands: str
    sensitivities: str
    attitude: int                # -100 ~ +100
    stance_label: str
    reason: str
    likely_actions: str
    influence: int               # 1~4
    risk_tilt: int               # 0~4
    judgment_basis: str
    triggers: List[str] = field(default_factory=list)
    # ---------- V4.0 扩展字段（基础身份扩展） ----------
    age_range: str = ""          # 例：18-22 / 30-40 / 45-55
    is_dorm: str = ""            # 是 / 否 / 部分时间
    common_scenes: List[str] = field(default_factory=list)  # 宿舍/教室/图书馆...
    sleep_type: str = ""         # 早睡型/夜猫型/规律型/随机型
    # ---------- V4.0 行为特征 ----------
    trajectory: str = ""         # 一日典型活动轨迹
    contact_frequency: str = ""  # 与规则接触频率
    info_channels: List[str] = field(default_factory=list)  # 信息获取渠道
    expression: str = ""         # 表达意见方式
    # ---------- V4.0 心理与诉求 ----------
    core_need: str = ""          # 核心需求
    top_concern: str = ""        # 最大担忧
    unacceptable: str = ""       # 最不能接受
    desired_compensation: str = ""  # 最希望得到的补偿
    school_trust: str = ""       # 对学校管理信任程度
    peer_tolerance: str = ""     # 对同学行为的容忍度
    risk_sensitivity: str = ""   # 风险敏感度
    # ---------- V4.0 行为预测 ----------
    first_reaction: str = ""     # 规则发布后第一反应
    short_term_change: str = ""  # 短期行为变化
    mid_term_change: str = ""    # 中期行为变化
    who_they_influence: str = "" # 可能影响谁
    chain_reaction: str = ""     # 可能引发的连锁反应
    final_direction: str = ""    # 对最终结果的影响方向
    # ---------- V4.0 代表性说明 ----------
    representative_for: str = "" # 该人物代表哪一类真实群体
    ratio_at_school: str = ""    # 在虚拟学校中的大致占比
    why_selected: str = ""       # 为什么被系统选为重点
    keywords: List[str] = field(default_factory=list)   # 3 个核心关键词
    one_line_bio: str = ""       # 一句话人物简介

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# 5 大类 · 30+ 虚拟角色原型
# ---------------------------------------------------------------------------

STUDENTS: List[Persona] = [
    Persona(
        id="stu_freshman", name="林一诺", archetype="大一新生", category="学生群体",
        grade_or_role="本科一年级",
        behavior="刚入学，对宿舍规则作息还在适应期；晚自习结束后回宿舍时间较早或较晚均有；社交活跃，喜欢参与校园活动",
        demands="希望快速融入新环境、需要明确的生活指引、安全感与归属感",
        sensitivities="陌生环境适应、宿舍人际关系、作息差异",
        attitude=+45, stance_label="支持",
        reason="取消宵禁后作息自由，回到宿舍后能与新同学继续交流、参加社团活动，减少因晚归被登记的焦虑",
        likely_actions="积极评价、与室友讨论时分享正面体验、参与校园相关话题讨论",
        influence=1, risk_tilt=1,
        judgment_basis="新生群体对『规则灵活化』普遍有正面感知，但执行能力弱、影响有限",
        triggers=["宵禁", "宿舍", "门禁", "作息", "晚归", "新生", "入学"],
    ),
    Persona(
        id="stu_dorm", name="陈思源", archetype="普通住校生", category="学生群体",
        grade_or_role="本科二/三年级",
        behavior="日常在宿舍生活，参与正常课程；偶尔因实习/社团晚归；周末出行较多",
        demands="学习与休息平衡、个人空间、灵活的门禁时间",
        sensitivities="宿舍安静度、室友作息、考试周复习空间",
        attitude=+58, stance_label="支持",
        reason="住校生受规则直接影响，取消宵禁直接提升日常自由度，尤其在实习/社团场景下不再担心晚归记录",
        likely_actions="在寝室群内传播支持态度、配合学校登记流程、参加试点方案",
        influence=2, risk_tilt=1,
        judgment_basis="住校生是『宿舍管理』类规则的最大直接受影响群体，权重最高",
        triggers=["宵禁", "宿舍", "门禁", "晚归", "住校", "作息", "自习"],
        # ---- V4.0 ----
        age_range="19-21",
        is_dorm="是",
        common_scenes=["宿舍", "教室", "图书馆", "食堂"],
        sleep_type="规律型",
        trajectory="07:30 起床 → 08:00 早餐 → 08:30-12:00 课程 → 12:00 午餐 → 13:30-17:30 课程/自习 → 18:00 晚餐 → 19:00-22:00 自习/社团 → 22:30 回宿舍",
        contact_frequency="极高",
        info_channels=["班级群", "寝室群", "校园公众号", "辅导员通知"],
        expression="问卷、私下吐槽、寝室群讨论、找辅导员",
        core_need="自由出入宿舍 / 灵活时间",
        top_concern="取消宵禁后宿舍纪律变松",
        unacceptable="宿舍秩序失控、夜间安全无保障",
        desired_compensation="晚归登记豁免 / 宿舍门禁不记档",
        school_trust="中高",
        peer_tolerance="中高",
        risk_sensitivity="中",
        first_reaction="朋友圈分享对取消宵禁的看法，班级群讨论",
        short_term_change="偶尔晚归不再担心登记",
        mid_term_change="晚上外出频率轻度上升",
        who_they_influence="同班同学 / 室友",
        chain_reaction="→ 带动其他住校生放松对门禁的警惕",
        final_direction="推高总体支持度",
        representative_for="占学校最大比例的核心学生群体",
        ratio_at_school="约 22-27%",
        why_selected="任何宿舍规则变化的最大权重样本",
        keywords=["住校生", "门禁", "晚归"],
        one_line_bio="普通住校本科生，日常平衡课程与宿舍生活，宵禁取消直接利好",
    ),
    Persona(
        id="stu_commuter", name="赵行舟", archetype="走读生", category="学生群体",
        grade_or_role="本科或研究生",
        behavior="每天通勤，宿舍仅作午休或不上课日使用；受门禁规则影响较小但关心宿舍资源分配",
        demands="通勤便利、宿舍资源（淋浴/午休空间）、家庭作息",
        sensitivities="宿舍资源紧张、通勤时间成本、家校沟通",
        attitude=+10, stance_label="中立偏支持",
        reason="走读生基本不受宵禁影响，但希望取消宵禁后宿舍资源能更合理分配",
        likely_actions="关注但不直接参与、宿舍群保持中立",
        influence=1, risk_tilt=0,
        judgment_basis="走读生对宿舍规则『中立』、但对宿舍资源分配话题会关注",
        triggers=["宿舍", "门禁", "作息", "走读"],
    ),
    Persona(
        id="stu_senior", name="姜末", archetype="毕业生", category="学生群体",
        grade_or_role="本科四年级或研究生",
        behavior="毕业论文/求职/考研多重压力，常在实验室/图书馆/校外活动到深夜",
        demands="灵活时间、不被打扰的论文写作空间、毕业流程便利",
        sensitivities="毕业流程效率、导师要求、求职时间窗口",
        attitude=+72, stance_label="强烈支持",
        reason="毕业生对『灵活作息』需求最强，取消宵禁能显著降低『晚归被登记影响毕业流程』的隐性风险",
        likely_actions="积极表达支持、向学校就业部门/导师反馈",
        influence=2, risk_tilt=0,
        judgment_basis="毕业生群体对『时间灵活化』诉求显著，但人群占比小",
        triggers=["宵禁", "晚归", "宿舍", "门禁", "毕业", "论文"],
    ),
    Persona(
        id="stu_grad_entrance", name="宋知秋", archetype="考研学生", category="学生群体",
        grade_or_role="本科三年级备考 / 研究生备考",
        behavior="长时间在图书馆/自习室/宿舍学习，作息极不规律；关注安静度与夜间通行",
        demands="深夜安静学习空间、自由出入宿舍与图书馆、考研复习时间",
        sensitivities="自习空间、宿舍噪音、室友作息",
        attitude=+65, stance_label="支持",
        reason="考研学生有深夜复习刚需，取消宵禁减少『学习被中断』的焦虑",
        likely_actions="校园论坛/小红书发帖支持、宿舍群内呼吁延长图书馆开放时间",
        influence=2, risk_tilt=0,
        judgment_basis="考研学生群体在『学习场景』下对宵禁取消有明显需求",
        triggers=["宵禁", "自习", "图书馆", "宿舍", "晚归", "作息"],
    ),
    Persona(
        id="stu_cadre", name="许澄", archetype="学生干部", category="学生群体",
        grade_or_role="学生会/研究生会/班级委员",
        behavior="上传下达，组织活动；与辅导员/班主任联系频繁；在学生群体中具有『舆论放大』能力",
        demands="活动空间、学生反馈通道、与学校沟通的渠道",
        sensitivities="学生诉求被忽视、活动审批、活动空间",
        attitude=+30, stance_label="中立偏支持",
        reason="学生干部对学校决策『执行理解』较强，取消宵禁对组织夜间活动有利",
        likely_actions="组织问卷收集意见、向辅导员反映、与社团联合发起讨论",
        influence=3, risk_tilt=1,
        judgment_basis="学生干部是『少数群体放大器』，虽占比小但影响力等级高、舆情能力强",
        triggers=["宵禁", "宿舍", "门禁", "学生", "活动", "舆情", "调研"],
        # ---- V4.0 ----
        age_range="20-24",
        is_dorm="是",
        common_scenes=["学生会办公室", "班级群", "活动室"],
        sleep_type="规律型",
        trajectory="07:30 起床 → 08:30 课程 → 12:00 午餐 → 13:30-17:30 课程 / 学生工作 → 18:00 晚餐 → 19:00-22:00 学生会议 / 活动组织 → 23:00 回宿舍",
        contact_frequency="高",
        info_channels=["班级群", "学生工作群", "辅导员通知", "校园公众号"],
        expression="问卷、组织调研、班级群讨论、与辅导员沟通",
        core_need="上传下达通道顺畅",
        top_concern="学生诉求被忽视 / 班级分歧扩大",
        unacceptable="被同学当成『学校代言人』",
        desired_compensation="活动审批简化 / 学生反馈被采纳",
        school_trust="高",
        peer_tolerance="高",
        risk_sensitivity="中",
        first_reaction="班级群收集意见，与辅导员沟通",
        short_term_change="组织班级讨论，整理意见",
        mid_term_change="成为班级意见的『传声筒』",
        who_they_influence="班级群体 / 辅导员",
        chain_reaction="→ 班级舆论扩散 → 辅导员向学院反映",
        final_direction="放大或收束舆论的关键节点",
        representative_for="少数高影响力的『放大器』人群",
        ratio_at_school="约 4-5%",
        why_selected="影响力等级 3，决定舆情扩散路径",
        keywords=["学生干部", "放大器", "中立"],
        one_line_bio="学生会/班委成员，担任学生与学校的桥梁与放大器",
    ),
    Persona(
        id="stu_club", name="徐漾", archetype="社团活跃学生", category="学生群体",
        grade_or_role="本科或研究生",
        behavior="深度参与社团活动/竞赛/排练，常在 22 点后返回宿舍",
        demands="活动空间、社团经费、活动审批效率",
        sensitivities="社团活动场地、跨校区活动、晚归登记",
        attitude=+62, stance_label="支持",
        reason="社团活动常晚于 22 点，取消宵禁避免频繁晚归登记",
        likely_actions="社团群内讨论、参加学校试点方案、撰写反馈",
        influence=2, risk_tilt=1,
        judgment_basis="社团活跃学生群体在『门禁时间』上有明确需求，但占比较低",
        triggers=["宵禁", "晚归", "社团", "活动", "宿舍", "门禁"],
    ),
    Persona(
        id="stu_risk_fail", name="裴学之", archetype="挂科风险学生", category="学生群体",
        grade_or_role="本科二/三年级",
        behavior="学习投入不足或方法不当；作息混乱；可能在宿舍违规用电、晚归频率高",
        demands="补考机会、学业预警后的恢复通道、心理疏导",
        sensitivities="学业预警、家长沟通、心理压力",
        attitude=+20, stance_label="中立",
        reason="取消宵禁对挂科风险学生而言减少了『晚归记录影响综测』的隐性压力",
        likely_actions="被动接受、可能借机更晚归",
        influence=1, risk_tilt=3,
        judgment_basis="挂科风险学生群体是『漏洞利用』的潜在人群，风险倾向中等",
        triggers=["宵禁", "晚归", "门禁", "综测", "宿舍"],
    ),
    Persona(
        id="stu_low_income", name="夏槐安", archetype="贫困生", category="学生群体",
        grade_or_role="本科或研究生",
        behavior="课余时间兼职或勤工俭学；可能晚归；经济压力下对外宿打工敏感",
        demands="勤工俭学机会、奖助学金公平、对经济信息的知情权",
        sensitivities="奖助学金评定、信息公开、隐私",
        attitude=+15, stance_label="中立",
        reason="取消宵禁能减少勤工俭学晚归登记的压力",
        likely_actions="通过班级群保持低调",
        influence=1, risk_tilt=1,
        judgment_basis="贫困生群体对宵禁影响弱，但与『奖助学金/隐私』话题强相关",
        triggers=["晚归", "宿舍", "门禁", "奖助", "兼职"],
    ),
    Persona(
        id="stu_intl", name="David / 大卫·K", archetype="留学生", category="学生群体",
        grade_or_role="本科或研究生，国际生",
        behavior="受文化差异影响，作息时间与中国学生不同；外宿/校外居住较多",
        demands="文化适应、住宿选择、跨文化交流机会",
        sensitivities="签证/居留、文化差异、校外住宿合规",
        attitude=+50, stance_label="支持",
        reason="留学生有跨时区作息习惯，取消宵禁减少『违规感』",
        likely_actions="国际学生群讨论、可能向留学生办公室反馈",
        influence=1, risk_tilt=0,
        judgment_basis="留学生占比小，但需求与国内学生不同，校方沟通成本高",
        triggers=["宵禁", "门禁", "住宿", "留学生"],
    ),
    Persona(
        id="stu_often_late", name="柳夜行", archetype="经常晚归学生", category="学生群体",
        grade_or_role="本科或研究生",
        behavior="晚归频率高（每周 3 次以上）；可能涉及兼职、社团、社交、外宿未报备",
        demands="减少晚归登记后果、外宿灵活性",
        sensitivities="晚归记录、综测、保研",
        attitude=+88, stance_label="强烈支持",
        reason="取消宵禁对其『晚归合规化』有直接利好，可能钻规则空子长期外宿",
        likely_actions="支持规则调整、借机长期外宿规避住宿费（潜在漏洞）",
        influence=2, risk_tilt=4,
        judgment_basis="经常晚归学生是『漏洞利用』最高风险群体，风险倾向极高",
        triggers=["宵禁", "晚归", "门禁", "外宿", "住宿"],
        # ---- V4.0 ----
        age_range="19-23",
        is_dorm="是（但频繁外宿）",
        common_scenes=["校门口", "周边商圈", "宿舍(较少)"],
        sleep_type="夜猫型",
        trajectory="10:00 后起床 → 11:00 课程/自由 → 14:00-17:30 自由 → 18:00 晚餐 → 19:00-02:00 社交/兼职/外宿",
        contact_frequency="极高",
        info_channels=["同学口口相传", "社交媒体", "宿舍群"],
        expression="朋友圈、小红书私下发文、宿舍群质疑校规",
        core_need="自由出入与外宿合规",
        top_concern="被抓到外宿导致纪律处分",
        unacceptable="晚归影响综测、保研",
        desired_compensation="晚归记录不入档",
        school_trust="中低",
        peer_tolerance="高",
        risk_sensitivity="低",
        first_reaction="校规群内欢呼，朋友圈转发",
        short_term_change="晚归频率明显上升，可能长期外宿",
        mid_term_change="若规则不严，可能持续规避住宿费",
        who_they_influence="同学群体 / 宿舍楼",
        chain_reaction="→ 宿管登记压力 ↑ → 作息规律学生投诉 ↑",
        final_direction="推高漏洞风险与舆情",
        representative_for="规则灵活性最强的少数群体",
        ratio_at_school="约 2-5%",
        why_selected="漏洞风险最高样本，决定『漏洞风险』指标",
        keywords=["晚归", "外宿", "高风险"],
        one_line_bio="晚归高频、对新规欢呼，但也是规则空子的高风险代表",
    ),
    Persona(
        id="stu_regular", name="苏时与", archetype="作息规律学生", category="学生群体",
        grade_or_role="本科或研究生",
        behavior="作息规律，重视宿舍安静度与个人空间；对外宿/晚归产生的噪音敏感",
        demands="宿舍安静度、休息权、睡眠质量",
        sensitivities="噪音、外宿管理、保卫巡查",
        attitude=-58, stance_label="反对",
        reason="取消宵禁后晚归者增多，宿舍夜间噪音风险上升，影响其睡眠与学习",
        likely_actions="投诉、向辅导员反映、可能发起联名信",
        influence=2, risk_tilt=2,
        judgment_basis="作息规律学生对宵禁取消『反对强烈』，虽占比不一定最高但反对强度高",
        triggers=["宵禁", "晚归", "宿舍", "噪音", "作息", "门禁"],
        # ---- V4.0 ----
        age_range="19-23",
        is_dorm="是",
        common_scenes=["宿舍", "图书馆", "教室"],
        sleep_type="早睡型",
        trajectory="06:30 起床 → 07:30 早餐 → 08:00-12:00 课程 → 12:00 午餐午休 → 13:30-17:30 课程/自习 → 18:00 晚餐 → 19:00-21:30 自习 → 22:00 回宿舍 → 23:00 熄灯",
        contact_frequency="高",
        info_channels=["辅导员通知", "班级群", "校园公众号"],
        expression="私下吐槽、投诉、找辅导员、可能联名信",
        core_need="安静的宿舍环境",
        top_concern="夜间噪音与室友作息冲突",
        unacceptable="室友深夜进出 / 长期外宿后回宿舍",
        desired_compensation="晚归者需登记 / 楼层门禁保留",
        school_trust="中",
        peer_tolerance="低",
        risk_sensitivity="中",
        first_reaction="担心宿舍噪音，第一时间在寝室群发声",
        short_term_change="投诉频次上升",
        mid_term_change="可能联名要求恢复宵禁或加严门禁",
        who_they_influence="同楼层/同宿舍同学",
        chain_reaction="→ 辅导员收到投诉 → 学院层面干预",
        final_direction="推高反对度与舆情",
        representative_for="重视安静宿舍环境的住校群体",
        ratio_at_school="约 3-4%",
        why_selected="反对强度最高，决定『反对度』指标",
        keywords=["反对", "作息", "安静"],
        one_line_bio="作息规律的住校本科生，反对新规对宿舍安静的潜在威胁",
    ),
    Persona(
        id="stu_intern", name="陆向北", archetype="实习学生", category="学生群体",
        grade_or_role="本科四年级或研究生",
        behavior="在外实习，作息依公司时间，可能跨城通勤或短期住校",
        demands="弹性住宿、实习证明流程、与学校沟通",
        sensitivities="实习时间冲突、外宿报备",
        attitude=+75, stance_label="强烈支持",
        reason="实习常晚归，取消宵禁减少『晚归登记影响毕业/评优』的隐性风险",
        likely_actions="积极反馈、与学院沟通",
        influence=2, risk_tilt=1,
        judgment_basis="实习学生群体时间需求灵活、对宵禁取消有明显利好",
        triggers=["宵禁", "晚归", "门禁", "实习", "外宿"],
    ),
    Persona(
        id="stu_parttime", name="宋暖", archetype="兼职学生", category="学生群体",
        grade_or_role="本科或研究生",
        behavior="课余在校园内外兼职（咖啡店/家教/校园勤工岗），晚归频率中等",
        demands="灵活时间、兼职渠道、宿舍安静",
        sensitivities="晚归登记、宿舍资源",
        attitude=+50, stance_label="支持",
        reason="兼职晚归被规则合规化，避免与课业冲突",
        likely_actions="兼职群内反馈",
        influence=1, risk_tilt=1,
        judgment_basis="兼职学生群体与晚归场景中度相关",
        triggers=["宵禁", "晚归", "门禁", "兼职"],
    ),
]


TEACHERS: List[Persona] = [
    Persona(
        id="tch_pub", name="沈砚之", archetype="公共课教师", category="教师群体",
        grade_or_role="讲师/副教授",
        behavior="承担多班公共课，与学生接触面广；不直接管理宿舍，但关心学生作息对课堂表现的影响",
        demands="课堂秩序、教学反馈",
        sensitivities="学生迟到、缺课、课堂注意力",
        attitude=+15, stance_label="中立偏支持",
        reason="取消宵禁对课堂表现的影响有限，整体支持『学生自主管理』",
        likely_actions="在教研场合表态支持",
        influence=2, risk_tilt=0,
        judgment_basis="公共课教师对宿舍规则态度中立偏支持，影响力一般",
        triggers=["宵禁", "门禁", "学生管理"],
    ),
    Persona(
        id="tch_pro", name="周牧", archetype="专业课教师", category="教师群体",
        grade_or_role="教授/副教授",
        behavior="负责专业课与毕业论文指导；常与学生一对一沟通至深夜",
        demands="科研时间、毕业论文质量",
        sensitivities="学生时间灵活度、实验室使用",
        attitude=+40, stance_label="支持",
        reason="专业课教师希望学生有更灵活时间完成实验/论文",
        likely_actions="在学院教学会议表态",
        influence=2, risk_tilt=0,
        judgment_basis="专业课教师与毕业论文场景直接相关",
        triggers=["宵禁", "晚归", "论文", "实验室"],
    ),
    Persona(
        id="tch_head", name="蒋荷", archetype="班主任", category="教师群体",
        grade_or_role="讲师/辅导员兼任",
        behavior="对班级学生整体负责；常处理宿舍矛盾、心理异常等事务",
        demands="学生安全、信息通道、班级稳定",
        sensitivities="宿舍矛盾、突发事件、学生安全",
        attitude=-30, stance_label="中立偏反对",
        reason="班主任担心取消宵禁后学生晚归频次上升、夜间突发事件增多",
        likely_actions="组织班会收集意见、向学院反映",
        influence=3, risk_tilt=2,
        judgment_basis="班主任是『日常安全责任方』，影响力中等偏上、风险关注高",
        triggers=["宵禁", "晚归", "宿舍", "门禁", "安全", "班主任"],
    ),
    Persona(
        id="tch_mentor", name="萧知白", archetype="导师", category="教师群体",
        grade_or_role="研究生导师",
        behavior="指导研究生科研，与学生一对一沟通频繁；关心科研进度与实验室安全",
        demands="科研进度、实验室使用、研究生培养质量",
        sensitivities="实验室安全、研究生心理",
        attitude=+30, stance_label="支持",
        reason="研究生常因科研晚归，取消宵禁契合实际需求",
        likely_actions="在学院内部支持、向研究生办公室反馈",
        influence=2, risk_tilt=1,
        judgment_basis="导师群体对研究生晚归持『务实支持』态度",
        triggers=["宵禁", "晚归", "实验室", "门禁", "研究生"],
    ),
    Persona(
        id="tch_lab", name="祁溪", archetype="实验室老师", category="教师群体",
        grade_or_role="实验员/实验室负责人",
        behavior="管理实验室安全与设备；与深夜实验的研究生联系密切",
        demands="实验室安全、设备维护、夜间准入",
        sensitivities="实验室违规、夜间安全",
        attitude=+10, stance_label="中立",
        reason="实验室夜间准入规则独立于宿舍宵禁",
        likely_actions="按实验室安全规范执行",
        influence=2, risk_tilt=1,
        judgment_basis="实验室教师对宿舍规则弱相关、对实验室安全规则强相关",
        triggers=["实验室", "宵禁", "门禁", "安全"],
    ),
    Persona(
        id="tch_admin_teach", name="程序", archetype="行政兼课教师", category="教师群体",
        grade_or_role="行政岗位兼课教师",
        behavior="承担部分行政事务 + 部分课程教学；与学校政策制定间接关联",
        demands="教学秩序、政策一致性",
        sensitivities="政策合规性",
        attitude=0, stance_label="中立",
        reason="行政兼课教师更关注政策一致性，对规则改变持中立态度",
        likely_actions="按学校政策执行",
        influence=2, risk_tilt=0,
        judgment_basis="行政兼课教师作为『政策传导方』影响力中等",
        triggers=["政策", "门禁", "管理"],
    ),
]


MANAGEMENT: List[Persona] = [
    Persona(
        id="mgr_counselor", name="韩叙", archetype="辅导员", category="管理人员",
        grade_or_role="学院辅导员",
        behavior="处理学生日常事务，包括宿舍矛盾、心理异常、突发事件；与学生接触最频繁",
        demands="学生安全、突发事件响应、信息通道",
        sensitivities="学生安全、突发事件、舆情",
        attitude=-25, stance_label="中立偏反对",
        reason="取消宵禁会增加辅导员夜间突发响应工作量",
        likely_actions="向学院反映、在学工例会讨论",
        influence=3, risk_tilt=3,
        judgment_basis="辅导员是『执行压力』核心承担方，影响力中等偏高、风险关注高",
        triggers=["宵禁", "晚归", "宿舍", "门禁", "安全", "辅导员"],
        # ---- V4.0 ----
        age_range="28-40",
        is_dorm="否（除值班）",
        common_scenes=["办公室", "学生宿舍", "学院会议室"],
        sleep_type="规律型",
        trajectory="08:30 到岗 → 09:00 处理班级事务 → 11:30 午餐 → 13:30 处理突发事件 / 走访宿舍 → 17:30 下班 → 19:00 班会 / 宿舍走访 → 22:00 下班（轮值班除外）",
        contact_frequency="极高",
        info_channels=["学院群", "班级群", "学生处通知", "电话"],
        expression="学工例会、班级群、个别谈心",
        core_need="安全责任清晰、可控",
        top_concern="突发事件追责到自己",
        unacceptable="夜间无人响应 / 责任全压在辅导员",
        desired_compensation="完善应急预案 / 增加保安支持",
        school_trust="中高",
        peer_tolerance="中",
        risk_sensitivity="高",
        first_reaction="学工例会上讨论，要求应急预案",
        short_term_change="夜间应急电话增多",
        mid_term_change="可能申请轮值制度调整",
        who_they_influence="学生处 / 学院书记 / 学生群体",
        chain_reaction="→ 学生处接信息 → 学院层面调整规则",
        final_direction="推动学校二次修改规则",
        representative_for="日常安全责任承担方",
        ratio_at_school="约 1.2-1.4%",
        why_selected="桥梁角色：上接学院、下连学生",
        keywords=["辅导员", "中立", "桥梁"],
        one_line_bio="学院辅导员，处于学校与学生的中间位置，平衡两方诉求",
    ),
    Persona(
        id="mgr_secretary", name="厉明远", archetype="学院书记", category="管理人员",
        grade_or_role="学院党委书记",
        behavior="统筹学院学生工作、思政教育、突发事件应对；与学校决策层直接对接",
        demands="学生稳定、思政教育、舆情可控",
        sensitivities="学生群体性事件、舆情",
        attitude=-10, stance_label="中立",
        reason="学院书记关注全局稳定，对宿舍规则调整持『风险评估后支持』态度",
        likely_actions="推动学院层面试点方案、要求风险预案",
        influence=4, risk_tilt=3,
        judgment_basis="学院书记是『决策相关方』，影响力等级最高、风险评估视角",
        triggers=["宵禁", "宿舍", "舆情", "学生管理"],
    ),
    Persona(
        id="mgr_academic", name="宋远", archetype="教务处老师", category="管理人员",
        grade_or_role="教务处学籍/考务管理",
        behavior="管理学籍、考试、教学安排；不直接管宿舍，但关心课堂出勤与教学秩序",
        demands="教学秩序、出勤合规",
        sensitivities="学生出勤、考务合规",
        attitude=0, stance_label="中立",
        reason="教务处与宿舍规则弱相关",
        likely_actions="关注但不主动参与",
        influence=2, risk_tilt=0,
        judgment_basis="教务处对宿舍规则弱相关",
        triggers=["教学", "出勤", "课堂"],
    ),
    Persona(
        id="mgr_student_affairs", name="容止", archetype="学生处老师", category="管理人员",
        grade_or_role="学生处副处长/科长",
        behavior="统筹全校学生事务、宿舍管理、突发事件；与辅导员、宿管对接",
        demands="宿舍管理规范、突发事件可控",
        sensitivities="宿舍矛盾、舆情、突发",
        attitude=-15, stance_label="中立偏反对",
        reason="学生处需要风险可控的宿舍管理",
        likely_actions="推动学校层面试点方案",
        influence=4, risk_tilt=3,
        judgment_basis="学生处是『宿舍规则核心制定方』，影响力高、风险评估能力强",
        triggers=["宵禁", "宿舍", "门禁", "学生管理"],
    ),
    Persona(
        id="mgr_dorm", name="何宿", archetype="宿管人员", category="管理人员",
        grade_or_role="宿舍管理员",
        behavior="日常负责宿舍楼门禁、巡查、登记；与晚归学生直接对接；执行规则的『最末端』",
        demands="门禁执行规范、减少登记工作量、宿舍安全",
        sensitivities="门禁设备、晚归登记工作量",
        attitude=-72, stance_label="强烈反对",
        reason="取消宵禁直接削弱宿管的『登记管控』职能，自身工作量与权威同时下降",
        likely_actions="向后勤/学生处反映、要求明确替代管理方案",
        influence=2, risk_tilt=2,
        judgment_basis="宿管是『执行难度』核心承担方，强烈反对取消规则",
        triggers=["宵禁", "门禁", "晚归", "宿舍", "宿管"],
        # ---- V4.0 ----
        age_range="45-60",
        is_dorm="是（值班）",
        common_scenes=["宿舍楼值班室", "校门口", "宿舍楼栋"],
        sleep_type="夜班轮换",
        trajectory="07:00 起床 → 08:00 交接班 → 08:30 楼栋巡查 → 12:00 午餐 → 14:00 登记/巡查 → 18:00 晚餐 → 19:30 值班登记晚归 → 23:00 关楼栋门 → 02:00 应急响应",
        contact_frequency="极高（执行末端）",
        info_channels=["学生处通知", "楼栋微信群", "工作例会"],
        expression="工作汇报、向上级反映、与学生当面对话",
        core_need="工作职责清晰 / 工作量不剧增",
        top_concern="夜间安全事件追责到自己身上",
        unacceptable="门禁完全放开而无人力补充",
        desired_compensation="增加保安 / 明确替代管理方案",
        school_trust="中高",
        peer_tolerance="中",
        risk_sensitivity="高",
        first_reaction="强烈反对，要求明确替代方案",
        short_term_change="登记工作量上升，怨言增多",
        mid_term_change="可能轮岗或离岗，执行风险进一步加大",
        who_they_influence="学生处 / 后勤 / 保卫处",
        chain_reaction="→ 后勤与学生处面临应急调整",
        final_direction="推高执行难度与公平性讨论",
        representative_for="门禁/宿舍规则的执行末端",
        ratio_at_school="约 0.8-1.4%",
        why_selected="决定『执行难度』的核心样本",
        keywords=["宿管", "执行压力", "反对"],
        one_line_bio="宿舍管理一线人员，规则变化直接改变其工作画像",
    ),
    Persona(
        id="mgr_security", name="罗卫", archetype="保卫处人员", category="管理人员",
        grade_or_role="校园保安/保卫处工作人员",
        behavior="夜间校园巡逻、出入登记、应急响应；与晚归学生、宿舍异常直接对接",
        demands="夜间安全可控、出入登记规范",
        sensitivities="夜间异常、突发事件",
        attitude=-45, stance_label="反对",
        reason="取消宵禁增加夜间异常事件发生概率，巡逻工作量上升",
        likely_actions="向保卫处反映、要求调整巡逻方案",
        influence=3, risk_tilt=3,
        judgment_basis="保卫处是『夜间安全核心责任方』，影响力中等偏高、风险关注高",
        triggers=["宵禁", "门禁", "晚归", "安全", "保卫"],
        # ---- V4.0 ----
        age_range="40-58",
        is_dorm="否",
        common_scenes=["校门口", "校园巡逻车", "保卫处值班室"],
        sleep_type="夜班轮换",
        trajectory="08:00 到岗 → 09:00 设备检查 → 12:00 午餐 → 14:00 巡查培训 → 18:00 交接 → 19:00 夜间巡逻 → 02:00 应急待命",
        contact_frequency="高（夜间）",
        info_channels=["保卫处群", "学院联系群", "对讲机"],
        expression="向保卫处汇报、与学生现场对话",
        core_need="夜间安全事件概率不上升",
        top_concern="突发事件无响应资源",
        unacceptable="夜间人手无增加却放开宵禁",
        desired_compensation="增加巡逻人手 / 监控覆盖",
        school_trust="中",
        peer_tolerance="中",
        risk_sensitivity="极高",
        first_reaction="要求调整巡逻方案与人手",
        short_term_change="夜间巡逻频次上升",
        mid_term_change="若不增加人手可能申请调岗",
        who_they_influence="学生处 / 校医院",
        chain_reaction="→ 校医院接报警 → 学生处调整通报",
        final_direction="推高风险指数与执行难度",
        representative_for="夜间安全的实际执行方",
        ratio_at_school="约 0.5-0.6%",
        why_selected="夜间安全链路核心节点",
        keywords=["保卫", "夜间", "风险"],
        one_line_bio="夜间校园安全执行者，取消宵禁直接增加其风险与工作量",
    ),
    Persona(
        id="mgr_library", name="庄墨", archetype="图书馆管理员", category="管理人员",
        grade_or_role="图书馆值班员/馆长",
        behavior="管理图书馆开闭馆、晚间自习空间；与考研学生、自习学生频繁接触",
        demands="自习空间管理、图书馆安全",
        sensitivities="夜间自习安全",
        attitude=+30, stance_label="支持",
        reason="图书馆管理员希望与宿舍规则同步调整（夜间延长开放）",
        likely_actions="调整图书馆夜间开放时间",
        influence=2, risk_tilt=1,
        judgment_basis="图书馆与宿舍规则『配套场景』，调整支持态度",
        triggers=["宵禁", "图书馆", "自习", "门禁"],
    ),
    Persona(
        id="mgr_canteen", name="钱勺", archetype="食堂管理人员", category="管理人员",
        grade_or_role="食堂经理/主任",
        behavior="管理食堂供餐时间、夜宵窗口；与晚归学生供餐场景对接",
        demands="食堂经营成本、夜间供餐管理",
        sensitivities="夜间供餐安全",
        attitude=+25, stance_label="支持",
        reason="晚归学生增加可能带动夜间供餐需求",
        likely_actions="评估夜宵窗口运营",
        influence=2, risk_tilt=1,
        judgment_basis="食堂管理与晚归场景中度相关",
        triggers=["宵禁", "晚归", "食堂"],
    ),
    Persona(
        id="mgr_clinic", name="苏白", archetype="校医院人员", category="管理人员",
        grade_or_role="校医院医生/护士",
        behavior="日常诊疗、夜间急诊值班；与突发事件、心理危机相关",
        demands="夜间急诊安全、医疗资源",
        sensitivities="夜间突发事件",
        attitude=-20, stance_label="中立偏反对",
        reason="担心取消宵禁后夜间突发事件增多、急诊压力上升",
        likely_actions="关注但不主动参与决策",
        influence=2, risk_tilt=2,
        judgment_basis="校医院对『夜间突发』风险敏感",
        triggers=["宵禁", "夜间", "安全", "应急"],
    ),
]


SERVICE: List[Persona] = [
    Persona(
        id="svc_canteen_staff", name="赵厨", archetype="食堂工作人员", category="校园服务人员",
        grade_or_role="食堂厨师/服务员",
        behavior="日常供餐、夜宵窗口工作；与学生错峰接触",
        demands="工作强度可控、宿舍临近供餐需求",
        sensitivities="夜间工作强度",
        attitude=+10, stance_label="中立",
        reason="取消宵禁对食堂工作人员工作强度影响有限",
        likely_actions="按排班工作",
        influence=1, risk_tilt=0,
        judgment_basis="食堂工作人员与晚归场景弱相关",
        triggers=["宵禁", "晚归", "食堂"],
    ),
    Persona(
        id="svc_clean", name="钱清", archetype="保洁人员", category="校园服务人员",
        grade_or_role="校园保洁员",
        behavior="负责宿舍楼/教学楼保洁；早晚班工作",
        demands="工作时间稳定、安全",
        sensitivities="夜间工作安全",
        attitude=0, stance_label="中立",
        reason="取消宵禁对保洁工作影响有限",
        likely_actions="按排班工作",
        influence=1, risk_tilt=0,
        judgment_basis="保洁人员与规则弱相关",
        triggers=["宿舍", "门禁"],
    ),
    Persona(
        id="svc_repair", name="孙修", archetype="维修人员", category="校园服务人员",
        grade_or_role="校园维修工",
        behavior="宿舍/教学楼设施维修；夜间应急维修",
        demands="夜间维修安全",
        sensitivities="夜间突发事件",
        attitude=-10, stance_label="中立",
        reason="担心晚归增多导致夜间报修增多",
        likely_actions="按需工作",
        influence=1, risk_tilt=1,
        judgment_basis="维修人员与规则弱相关",
        triggers=["宿舍", "门禁", "晚归"],
    ),
    Persona(
        id="svc_express", name="李递", archetype="快递站人员", category="校园服务人员",
        grade_or_role="校园快递站工作人员",
        behavior="管理校园快递收发；与学生取件高峰相关",
        demands="取件秩序、库房安全",
        sensitivities="库房夜间安全",
        attitude=0, stance_label="中立",
        reason="取消宵禁对快递站业务影响有限",
        likely_actions="按业务工作",
        influence=1, risk_tilt=0,
        judgment_basis="快递站与规则弱相关",
        triggers=["宿舍", "门禁"],
    ),
    Persona(
        id="svc_market", name="周铺", archetype="超市工作人员", category="校园服务人员",
        grade_or_role="校园超市店员",
        behavior="商品销售、夜间值班",
        demands="夜间经营秩序",
        sensitivities="夜间安全",
        attitude=+5, stance_label="中立",
        reason="晚归学生增加可能带动夜间销售",
        likely_actions="按经营工作",
        influence=1, risk_tilt=0,
        judgment_basis="超市与晚归场景弱相关",
        triggers=["晚归", "门禁"],
    ),
]


EXTERNAL: List[Persona] = [
    Persona(
        id="ext_parent", name="宋家长", archetype="家长", category="外部相关者",
        grade_or_role="学生家长",
        behavior="关心孩子在校安全、作息、学业；通过电话/微信/家长群了解学校动态",
        demands="孩子安全、作息规律、信息知情权",
        sensitivities="孩子安全、夜间异常",
        attitude=-30, stance_label="中立偏反对",
        reason="家长担心取消宵禁后孩子夜间安全风险上升",
        likely_actions="家长群讨论、致电辅导员/班主任",
        influence=3, risk_tilt=2,
        judgment_basis="家长不在校内但『舆情能力强』，对学校决策有间接影响",
        triggers=["宵禁", "晚归", "宿舍", "安全", "门禁"],
        # ---- V4.0 ----
        age_range="42-55",
        is_dorm="否",
        common_scenes=["家庭", "电话", "家长群"],
        sleep_type="夜猫型（关心孩子）",
        trajectory="工作 → 关注孩子在校动态 → 电话或微信询问 → 接孩子反馈",
        contact_frequency="高（家长群）",
        info_channels=["家长群", "电话", "朋友圈", "校园公众号"],
        expression="致电辅导员、家长群讨论、12345 投诉、媒体表达",
        core_need="孩子安全有保障",
        top_concern="取消宵禁后夜间安全事件",
        unacceptable="孩子在校突发意外无人负责",
        desired_compensation="学校加强夜间值班 / 应急通道",
        school_trust="中",
        peer_tolerance="中",
        risk_sensitivity="高",
        first_reaction="致电辅导员 / 家长群讨论",
        short_term_change="接孩子电话频次上升",
        mid_term_change="可能联名要求学校恢复规则",
        who_they_influence="学院书记 / 学校决策层",
        chain_reaction="→ 学院层面被动调整 → 媒体关注",
        final_direction="外部舆情关键变量",
        representative_for="校外舆情压力源",
        ratio_at_school="外部 0（虚拟占比）",
        why_selected="舆情能力强，能把校内事件扩散至校外",
        keywords=["家长", "安全", "舆情"],
        one_line_bio="不在校内但掌握舆情放大器，关心孩子安全",
    ),
    Persona(
        id="ext_alumni", name="校友", archetype="校友", category="外部相关者",
        grade_or_role="毕业生/校友",
        behavior="通过校友会、社交媒体关注母校动态；偶尔返校",
        demands="母校声誉、校友资源",
        sensitivities="母校声誉、舆情",
        attitude=+15, stance_label="中立偏支持",
        reason="校友多支持母校『现代化』调整",
        likely_actions="校友群讨论、转发",
        influence=2, risk_tilt=0,
        judgment_basis="校友占比小但『舆论传播能力强』",
        triggers=["学校", "管理"],
    ),
    Persona(
        id="ext_intern_org", name="实习单位", archetype="实习单位", category="外部相关者",
        grade_or_role="校企合作单位",
        behavior="接收实习生、参与校企合作项目；关心学生实习质量",
        demands="实习生质量、合作稳定",
        sensitivities="实习时间冲突",
        attitude=+45, stance_label="支持",
        reason="取消宵禁有利于学生按企业时间弹性实习",
        likely_actions="校企沟通中反馈",
        influence=2, risk_tilt=0,
        judgment_basis="实习单位与『实习时间』话题强相关",
        triggers=["实习", "晚归", "门禁"],
    ),
    Persona(
        id="ext_local_shop", name="周边商家", archetype="周边商家", category="外部相关者",
        grade_or_role="校园周边商铺/餐饮",
        behavior="经营学生消费场景；夜间经营受学生出行影响",
        demands="学生客流、夜间经营秩序",
        sensitivities="夜间经营秩序",
        attitude=+30, stance_label="支持",
        reason="晚归学生增加可能带动夜间消费",
        likely_actions="按经营调整",
        influence=1, risk_tilt=0,
        judgment_basis="周边商家与晚归场景中度相关",
        triggers=["晚归", "夜间"],
    ),
    Persona(
        id="ext_community", name="社区居民", archetype="社区居民", category="外部相关者",
        grade_or_role="学校周边社区居民",
        behavior="受学校周边交通、噪音、夜间学生外出影响",
        demands="社区安全、安静",
        sensitivities="夜间噪音、安全",
        attitude=-15, stance_label="中立偏反对",
        reason="担心晚归学生增多导致周边夜间噪音/治安问题",
        likely_actions="向街道反映",
        influence=1, risk_tilt=1,
        judgment_basis="社区居民与晚归场景弱相关、舆情影响中等",
        triggers=["晚归", "夜间", "宿舍"],
    ),
]


# ---------------------------------------------------------------------------
# 汇总字典 + 触发匹配函数
# ---------------------------------------------------------------------------

ALL_PERSONAS: List[Persona] = (
    STUDENTS + TEACHERS + MANAGEMENT + SERVICE + EXTERNAL
)


PERSONA_BY_ID: Dict[str, Persona] = {p.id: p for p in ALL_PERSONAS}


CATEGORY_LABEL = {
    "学生群体": "学生群体",
    "教师群体": "教师群体",
    "管理人员": "管理人员",
    "校园服务人员": "校园服务人员",
    "外部相关者": "外部相关者",
}


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def match_relevance(persona: Persona, content: str, category_hint: str = "") -> Tuple[str, float]:
    """
    返回 (相关性等级, 命中分数)：
    - "strong" : 至少 1 个 trigger 命中发布内容（或者人物敏感度与发布内容高度相关）
    - "weak"   : 同大类但无直接 trigger 命中
    - "dormant" : 弱相关，仅作『完整人口库』展示
    """
    text = _norm(content)
    hits = sum(1 for t in persona.triggers if _norm(t) in text)
    if hits >= 1:
        return "strong", float(hits)
    # 类目兜底：当 rule_category 是宿舍管理类、且人物类别与『管理执行』相关时，算 strong
    if category_hint in ("宿舍管理类",) and persona.category in ("管理人员", "校园服务人员"):
        return "strong", 0.5
    if persona.category == "学生群体" and category_hint in ("宿舍管理类",):
        return "strong", 0.5
    return "weak", 0.0


def list_personas() -> List[Dict[str, Any]]:
    return [p.to_dict() for p in ALL_PERSONAS]


def persona_summary_by_category() -> Dict[str, int]:
    out: Dict[str, int] = {k: 0 for k in CATEGORY_LABEL}
    for p in ALL_PERSONAS:
        out[p.category] = out.get(p.category, 0) + 1
    return out
