import re
from html import escape as _esc

from knowledge import kb

SCOPE_KEYS = ("小范围试点", "部分群体", "全体推行")
STRENGTH_KEYS = ("温和", "中等", "严格")
GOAL_KEYS = ("提高效率", "增加收益", "降低风险", "提升公平", "提高满意度")

# 第3步「补充规则属性」→ 推演参数表
GOAL_WEIGHTS = {
    "提高效率": {"efficiency": 1.0, "benefit": 0.7, "satisfaction": 0.5, "fairness": 0.4, "riskControl": 0.5},
    "增加收益": {"efficiency": 0.7, "benefit": 1.0, "satisfaction": 0.5, "fairness": 0.4, "riskControl": 0.4},
    "降低风险": {"efficiency": 0.5, "benefit": 0.4, "satisfaction": 0.5, "fairness": 0.6, "riskControl": 1.0},
    "提升公平": {"efficiency": 0.5, "benefit": 0.4, "satisfaction": 0.7, "fairness": 1.0, "riskControl": 0.7},
    "提高满意度": {"efficiency": 0.5, "benefit": 0.5, "satisfaction": 1.0, "fairness": 0.7, "riskControl": 0.5},
}
SCOPE_FACTOR = {"小范围试点": 0.2, "部分群体": 0.6, "全体推行": 1.0}
STRENGTH_FACTOR = {
    "温和": {"execution": 0.6, "resistance": 0.2, "riskControl": 0.5, "compliance": 0.6},
    "中等": {"execution": 0.8, "resistance": 0.4, "riskControl": 0.75, "compliance": 0.8},
    "严格": {"execution": 1.0, "resistance": 0.7, "riskControl": 1.0, "compliance": 0.9},
}

# 影响依据文案（结果页展示「本结果受以下规则属性影响」）
GOAL_BASIS = {
    "提高效率": "提高效率与收益权重，但降低公平和满意度权重。",
    "增加收益": "提高收益与效率权重，但降低风险控制权重。",
    "降低风险": "提高风险控制权重，但降低收益与效率权重。",
    "提升公平": "提高公平与满意度权重，但降低收益与效率权重。",
    "提高满意度": "提高满意度与公平权重，但相对降低效率与风险控制权重。",
}
SCOPE_BASIS = {
    "小范围试点": "缩小受影响人数、降低风险暴露与执行难度，但压低总收益并放大反馈价值。",
    "部分群体": "按部分群体规模计算受影响人数，风险、收益与成本处于中间水平。",
    "全体推行": "扩大受影响人数，同时放大收益、成本和风险，扩大舆情扩散与风险链长度。",
}
STRENGTH_BASIS = {
    "温和": "提高配合度与满意度，但执行与风险控制效果较弱，违规与漏洞利用概率偏高。",
    "中等": "执行与风险控制效果适中，抵触与管理成本处于中等水平。",
    "严格": "提高执行和风险控制效果，但增加抵触、管理成本和冲突风险。",
}

# 五类主体画像：key / 基础支持度 / 基础风险 / 脆弱性 / 人数权重 / 与规则相关系数
ROLE_PROFILE = [
    ("d", "直接受影响主体", 72, 58, 1.00, 0.30, 0.92),
    ("i", "间接受影响主体", 54, 48, 0.85, 0.24, 0.55),
    ("m", "管理执行主体", 61, 38, 0.70, 0.18, 0.72),
    ("v", "潜在受损主体", 24, 72, 1.25, 0.18, 0.80),
    ("h", "高风险行为主体", 82, 88, 1.50, 0.10, 0.95),
]

DIRECTIONS = [
    (("延长", "放宽", "扩大", "增加", "提高", "提升", "加强", "加大"), "放宽 / 提高"),
    (("缩短", "收紧", "压缩", "降低", "减少", "下调"), "收紧 / 降低"),
    (("取消", "废除"), "取消"),
    (("改为", "实行", "实施", "推行", "新增", "上线", "纳入", "升级"), "新增 / 变更"),
]


def detect(society_id, content, force=False):
    cur = kb.society(society_id)
    if cur is None:
        return {"status": "error", "message": "未知社会类型: %s" % society_id}
    best_cat, best_kw, best_count = None, None, 0
    for c in cur["cats"]:
        hits = [k for k in c["kw"] if k in content]
        if len(hits) > best_count:
            best_cat, best_kw, best_count = c, hits[0], len(hits)
    other = None
    for s in kb.SOC:
        if s["id"] == society_id:
            continue
        for c in s["cats"]:
            for k in c["kw"]:
                if k in content:
                    if other is None or _kw_count(s, content) > other["count"]:
                        other = {
                            "society_id": s["id"], "name": s["name"], "ico": s["ico"],
                            "category_name": c["name"], "kw": k, "count": _kw_count(s, content),
                        }
                    break
            if other and other["society_id"] == s["id"]:
                break
    if best_cat is None and other and other["count"] >= 2 and not force:
        return {
            "status": "mismatch",
            "current_society": {"id": cur["id"], "name": cur["name"], "ico": cur["ico"], "cats": len(cur["cats"])},
            "suggested": other,
            "message": "发布内容与当前社会类型的全部 %d 个规则类别均不匹配，而与「%s」的「%s」高度匹配（命中 %d 个关键词）。请重新确认社会类型，系统不会强行生成无关结果。" % (
                len(cur["cats"]), other["name"], other["category_name"], other["count"]),
        }
    inferred = best_cat is None
    if inferred:
        best_cat = cur["cats"][0]
    return {
        "status": "ok",
        "inferred": inferred,
        "matched_kw": None if inferred else best_kw,
        "society": {"id": cur["id"], "name": cur["name"], "ico": cur["ico"], "scope": cur["scope"],
                    "data": cur["data"], "groups": cur["groups"]},
        "category": _cat_view(best_cat),
        "subjects": _subjects(cur, best_cat),
        "benefits": list(best_cat["benefit"]),
        "costs": list(best_cat["cost"]),
        "risks": list(best_cat["risk"]),
        "data_needs": "支持度 / 风险感知 / 公平感知 / 行为意愿",
        "direction": _direction(content),
        "other_society": other,
    }


def _kw_count(s, content):
    return sum(1 for c in s["cats"] for k in c["kw"] if k in content)


def _cat_view(c):
    return {"name": c["name"], "desc": c["desc"], "lim": c["lim"], "soft": c["soft"]}


def _subjects(s, c):
    merged = dict(s["subj"])
    merged.update(c.get("subs") or {})
    return {"d": merged["d"], "i": merged["i"], "m": merged["m"], "v": merged["v"], "h": merged["h"]}


def _direction(content):
    for keys, label in DIRECTIONS:
        if any(k in content for k in keys):
            return label
    return "调整"


def rule_attribute_profile(goal, scope, strength):
    """第3步补充规则属性 → 推演参数（发布目标权重 / 发布范围因子 / 规则强度因子）。"""
    goal = goal if goal in GOAL_WEIGHTS else "提高满意度"
    scope = scope if scope in SCOPE_FACTOR else "部分群体"
    strength = strength if strength in STRENGTH_FACTOR else "中等"
    gw = GOAL_WEIGHTS[goal]
    sf = SCOPE_FACTOR[scope]
    st = STRENGTH_FACTOR[strength]
    return {
        "goal": goal, "scope": scope, "strength": strength,
        "goal_weights": dict(gw),
        "scope_factor": sf,
        "strength_factor": dict(st),
        "strength_risk_factor": round(1.6 - st["riskControl"], 2),
        "execution": st["execution"],
        "resistance": st["resistance"],
        "compliance": st["compliance"],
    }


def group_dynamics(goal="提高满意度", scope="部分群体", strength="中等", total_pop=100000):
    """核心计算：群体支持度_i = 基础支持度 + 目标匹配度 - 强度抵触度 - 范围公平损失；
    风险值_i = 基础风险 × scopeFactor × strengthRiskFactor × 群体脆弱性；
    综合支持度/风险 = Σ(值×人数) ÷ 总人数；受影响人数 = 总人数 × scopeFactor × 群体相关系数。"""
    ra = rule_attribute_profile(goal, scope, strength)
    gw, sf, srf = ra["goal_weights"], ra["scope_factor"], ra["strength_risk_factor"]
    resistance = ra["resistance"]
    r_sens = {"d": 0.5, "i": 0.4, "m": 0.6, "v": 1.2, "h": 1.0}
    rows, t_sup, t_risk, t_w, corr_sum = [], 0.0, 0.0, 0.0, 0.0
    for key, role, base_sup, base_risk, vuln, w, corr in ROLE_PROFILE:
        if key == "d":
            match = (gw["efficiency"] * 0.5 + gw["benefit"] * 0.3 + gw["satisfaction"] * 0.2) * 12 - 6
        elif key == "i":
            match = (gw["satisfaction"] * 0.5 + gw["fairness"] * 0.5) * 10 - 5
        elif key == "m":
            match = (gw["efficiency"] * 0.5 + gw["riskControl"] * 0.5) * 10 - 5
        elif key == "v":
            match = (gw["fairness"] * 0.6 + gw["satisfaction"] * 0.4) * 12 - 6
        else:
            match = (gw["efficiency"] * 0.3 - gw["riskControl"] * 0.7) * 8 - 4
        resist = resistance * 10 * r_sens[key]
        fl = sf * 6 * (1.0 if key == "v" else (0.6 if key == "i" else 0.3))
        support = max(5, min(95, round(base_sup + match - resist - fl, 1)))
        risk = max(3, min(98, round(base_risk * sf * srf * vuln, 1)))
        rows.append({"key": key, "role": role, "support": support, "risk": risk,
                     "weight": w, "corr": corr,
                     "goal_match": round(match, 1),
                     "strength_resistance": round(resist, 1),
                     "scope_fairness_loss": round(fl, 1)})
        t_sup += support * w
        t_risk += risk * w
        t_w += w
        corr_sum += corr * w
    corr_avg = corr_sum / t_w
    return {"groups": rows, "support": round(t_sup / t_w, 1), "risk": round(t_risk / t_w, 1),
            "affected": round(total_pop * sf * corr_avg), "total_pop": total_pop,
            "scope_factor": sf, "correlation": round(corr_avg, 2)}


def attribute_basis(goal, scope, strength):
    """影响依据：结果页「本结果受以下规则属性影响」。"""
    goal = goal if goal in GOAL_WEIGHTS else "提高满意度"
    scope = scope if scope in SCOPE_FACTOR else "部分群体"
    strength = strength if strength in STRENGTH_FACTOR else "中等"
    return {
        "goal": goal, "goal_effect": GOAL_BASIS[goal],
        "scope": scope, "scope_effect": SCOPE_BASIS[scope],
        "strength": strength, "strength_effect": STRENGTH_BASIS[strength],
    }


def attribute_contrast_test(society_id="school", category_name=None, data_source="系统内置模拟参数"):
    """控制变量测试：固定社会类型 / 发布内容 / 群体人数 / 数据来源，只改变一个属性比较前后结果。

    至少覆盖：提高效率 vs 提升公平；小范围试点 vs 全体推行；温和 vs 严格。
    若属性改变后所有结果完全不变，说明参数未接入成功。
    """
    if category_name is None:
        s, c = category_full(society_id, "")
        if c is None:
            return {"status": "error", "message": "未知社会类型: %s" % society_id}
        category_name = c["name"]
    base = {"goal": "提高效率", "scope": "部分群体", "strength": "中等"}
    pairs = [
        ("提高效率 vs 提升公平", {"goal": "提高效率"}, {"goal": "提升公平"}),
        ("小范围试点 vs 全体推行", {"scope": "小范围试点"}, {"scope": "全体推行"}),
        ("温和 vs 严格", {"strength": "温和"}, {"strength": "严格"}),
    ]
    keys = ["approve", "oppose", "risk", "fairness", "benefit", "cost", "behavior", "diffNum",
            "affected", "composite_support", "composite_risk", "chain_len", "best_plan"]

    def run(delta):
        g = delta.get("goal", base["goal"])
        sc = delta.get("scope", base["scope"])
        st = delta.get("strength", base["strength"])
        m = simulate_metrics(g, sc, st, data_source, None)
        dyn = group_dynamics(g, sc, st)
        chains = deduce_chains(society_id, category_name, g, sc, st)
        plans = generate_plans(society_id, category_name, m)
        return {
            "approve": m["approve"], "oppose": m["oppose"], "risk": m["risk"],
            "fairness": m["fairness"], "benefit": m["benefit"], "cost": m["cost"],
            "behavior": m["behavior"], "diffNum": m["diffNum"],
            "affected": dyn["affected"], "composite_support": dyn["support"],
            "composite_risk": dyn["risk"], "chain_len": len(chains["main"]),
            "best_plan": plans["rec"]["name"],
        }

    cases = []
    for name, a, b in pairs:
        ra, rb = run(a), run(b)
        changed = [k for k in keys if ra[k] != rb[k]]
        unchanged = [k for k in keys if ra[k] == rb[k]]
        cases.append({"case": name, "before": ra, "after": rb,
                      "changed": changed, "unchanged": unchanged,
                      "passed": len(changed) >= 3})
    return {"status": "ok", "total": len(cases),
            "passed": all(c["passed"] for c in cases), "cases": cases}


def category_full(society_id, category_name):
    s = kb.society(society_id)
    if s is None:
        return None, None
    for c in s["cats"]:
        if c["name"] == category_name:
            return s, c
    return s, s["cats"][0]


def build_questionnaire(society_id, category_name, content):
    s, c = category_full(society_id, category_name)
    if c is None:
        return []
    subs = _subjects(s, c)
    groups = s["groups"].split("、")[:8]
    plan_opts = ["原方案：直接全面推行", "温和方案：" + c["soft"], "限制方案：" + c["lim"],
                 "试点方案：先在" + s["scope"] + "试点，验证后推广"]
    ben_q = [["你认为它是否能实现「" + b + "」？", ["明显能", "部分能", "不能"], True] for b in c["benefit"][:3]]
    cost_q = [["你是否担心出现「" + x + "」？", ["非常担心", "有点担心", "不担心"], True] for x in c["cost"][:3]]
    risk_q = [["你认为是否会出现「" + x + "」？", ["很可能", "可能", "不太可能"], True] for x in c["risk"][:2]]
    vuln_q = [["你是否认为会有人利用「" + v + "」这类漏洞？", ["很可能", "可能", "不太可能"], True]
              for v in (c["vuln"][:2] if len(c["vuln"]) >= 2 else c["vuln"] + c["risk"][:2 - len(c["vuln"])])]
    return [
        {"name": "基本信息题", "ico": "👤", "qs": [
            ["你的身份属于哪一类？", groups, False],
            ["你与该规则/产品的关联程度如何？", ["密切相关", "有一定关联", "无直接关联"], False],
            ["你使用相关服务或资源的频率是多少？", ["每天使用", "每周数次", "偶尔使用", "几乎不使用"], False]]},
        {"name": "态度判断题", "ico": "⚖", "qs": [
            ["你是否支持「" + content + "」正式发布？", ["支持", "中立", "反对"], True],
            ["你认为「" + content + "」是否有必要？", ["非常有必要", "一般", "没有必要"], True],
            ["如果正式实施，你是否愿意配合？", ["愿意配合", "部分配合", "不愿意配合"], True]]},
        {"name": "收益感知题（来自本类别专属收益）", "ico": "📈", "qs": ben_q},
        {"name": "成本感知题（来自本类别专属成本）", "ico": "📉", "qs": cost_q},
        {"name": "公平性题（针对潜在受损主体）", "ico": "🤝", "qs": [
            ["你认为该规则对「" + subs["v"] + "」是否公平？", ["公平", "基本公平", "不太公平", "很不公平"], True],
            ["是否有某些群体会因此受到不利影响？", ["有", "可能有", "没有"], True],
            ["是否需要补偿或保护机制？", ["需要", "可酌情设置", "不需要"], True]]},
        {"name": "风险与漏洞题（来自本类别专属风险与漏洞）", "ico": "🕳", "qs": risk_q + vuln_q},
        {"name": "替代方案题（对应 4 个反事实方案）", "ico": "🔀", "qs": [
            ["你更支持哪种推行方式？", plan_opts, True],
            ["是否支持在推行中增加限制条件？", ["支持", "视情况", "不支持"], True],
            ["是否支持设置反馈与修正机制？", ["支持", "视情况", "不支持"], True]]},
    ]


def simulate_metrics(goal="提高满意度", scope="部分群体", strength="中等", data_source="", live=None):
    """推演指标：基础基线 + 发布目标(goalWeights) + 发布范围(scopeFactor) + 规则强度(strengthFactor) + 实时/公开数据校准。

    发布目标影响：可能收益/可能成本/群体支持度/满意度/公平感知/最终方案评分；
    发布范围影响：受影响人数/风险传播范围/总收益/总成本/舆情扩散/风险链长度/执行难度/公平性评价；
    规则强度影响：执行效果/规则遵守率/支持度/抵触程度/违规行为/管理成本/冲突风险/漏洞利用概率。
    """
    if goal not in GOAL_KEYS:
        goal = "提高满意度"
    if scope not in SCOPE_KEYS:
        scope = "部分群体"
    if strength not in STRENGTH_KEYS:
        strength = "中等"
    ra = rule_attribute_profile(goal, scope, strength)
    gw, sf, st = ra["goal_weights"], ra["scope_factor"], ra["strength_factor"]
    dyn = group_dynamics(goal, scope, strength)
    live_used = False
    live_info = {}
    if live and live.get("ok"):
        # 实时拉取成功：用来源页代表性比例做温和校准（与模板基线折中，避免单一页面占比失真）
        live_used = True
        v = float(live["value"])
        live_info = {"used": True, "value": v, "url": live.get("url", ""), "ms": live.get("ms", 0)}
    # 可能收益 / 可能成本 / 行为意愿 / 执行难度 / 公平感知（目标 × 范围 × 强度共同决定）
    benefit = 70 + round(gw["benefit"] * 10) + round(gw["efficiency"] * 4) \
        + (6 if scope == "全体推行" else -5 if scope == "小范围试点" else 0) \
        + round(st["execution"] * 5) - round(st["resistance"] * 6)
    cost = 45 + round(st["resistance"] * 30) \
        + (10 if scope == "全体推行" else -6 if scope == "小范围试点" else 0) \
        + round(gw["benefit"] * 3)
    behavior = 45 + round(st["compliance"] * 18) \
        + (8 if scope == "全体推行" else -4 if scope == "小范围试点" else 0) \
        + round(gw["satisfaction"] * 4)
    diffNum = 50 + round(st["execution"] * 12) \
        + (6 if scope == "全体推行" else -4 if scope == "小范围试点" else 0) \
        + round(gw["efficiency"] * 3) - round(gw["fairness"] * 3)
    fairness = 73 + round((gw["fairness"] - 0.5) * 12) \
        - (4 if scope == "全体推行" else -4 if scope == "小范围试点" else 0) \
        - round(st["resistance"] * 3)
    # 综合支持度 / 综合风险值：直接采用用户给定公式的加权结果
    goal_risk_mul = 1.1 - gw["riskControl"] * 0.1  # 降低风险目标小幅压降综合风险
    comp_sup, comp_risk = dyn["support"], round(dyn["risk"] * goal_risk_mul, 1)
    GOAL_POP = {"提高满意度": 14, "提高效率": 12, "增加收益": 8, "降低风险": 6, "提升公平": 4}
    approve = int(round(comp_sup + GOAL_POP[goal]))
    oppose = int(round(max(5.0, 100 - approve - 30 - st["resistance"] * 4)))
    risk = int(round(comp_risk))
    if live_used:
        v = live_info["value"]
        approve = int(round(max(35.0, min(88.0, approve + (v - 50) / 4.0))))
        oppose = int(round(max(8.0, min(40.0, oppose - (v - 50) / 6.0))))
        risk = int(round(max(15.0, min(85.0, risk + abs(v - 50) / 8.0))))
    elif data_source and data_source != "系统内置模拟参数":
        # 实时拉取不可用/未启用：回退公开数据校准基线
        approve += 2
        oppose -= 2
        risk -= 4
    approve = max(20, min(92, approve))
    oppose = max(5, min(55, oppose))
    risk = max(10, min(92, risk))
    benefit = max(30, min(95, benefit))
    cost = max(15, min(90, cost))
    behavior = max(15, min(90, behavior))
    diffNum = max(20, min(90, diffNum))
    fairness = max(35, min(95, fairness))
    diff = "偏高" if diffNum >= 62 else ("较低" if diffNum < 38 else "中等")
    hole = "偏高" if risk >= 50 else ("中等" if risk >= 35 else "较低")
    rec_plan = "试点方案" if risk >= 55 else ("限制方案" if risk >= 35 else "温和方案")
    src_label = data_source or "系统内置模拟参数"
    if live_used:
        basis = "实时拉取自公开数据源（%s），代表性比例 %s%%（耗时 %sms）" % (
            live_info["url"], live_info["value"], live_info["ms"])
    elif data_source:
        basis = "公开数据校准基线（实时拉取不可用，基于所选官方公开数据源预设校准）"
    else:
        basis = "系统内置模拟参数基线（基于场景模板推算）"
    return {"approve": approve, "oppose": oppose, "risk": risk, "fairness": fairness,
            "benefit": benefit, "cost": cost, "behavior": behavior, "diffNum": diffNum,
            "diff": diff, "hole": hole, "recPlan": rec_plan,
            "goal": goal, "scope": scope, "strength": strength,
            "data_source": src_label, "source_basis": basis, "live": live_info,
            "composite": {"support": comp_sup, "risk": comp_risk,
                          "affected": dyn["affected"], "total_pop": dyn["total_pop"],
                          "scope_factor": dyn["scope_factor"], "correlation": dyn["correlation"],
                          "groups": dyn["groups"]},
            "attributes": ra,
            "attribute_basis": attribute_basis(goal, scope, strength)}


def rec_desc(s, c, rec_plan):
    if rec_plan == "试点方案":
        return "先在" + s["scope"] + "试点，验证后再推广"
    if rec_plan == "限制方案":
        return c["lim"]
    if rec_plan == "温和方案":
        return c["soft"]
    return "直接全面推行"


def deduce_groups(society_id, category_name, goal="提高满意度", scope="部分群体", strength="中等"):
    """五类主体差异：支持度 = 基础支持度 + 目标匹配度 - 强度抵触度 - 范围公平损失；风险值随范围×强度×脆弱性变动。"""
    s, c = category_full(society_id, category_name)
    if c is None:
        return []
    subs = _subjects(s, c)
    dyn = group_dynamics(goal, scope, strength)
    role_map = {"d": "fb-green", "i": "fb-blue", "m": "fb-amber", "v": "fb-violet", "h": "fb-red"}
    roles = [
        {"role": "直接受影响主体", "tagCls": "tag-green", "att": "支持偏中立", "subj": subs["d"],
         "why": "直接关联，受益或受损取决于具体处境", "risk": "配合度随执行效果波动"},
        {"role": "间接受影响主体", "tagCls": "tag-blue", "att": "中立", "subj": subs["i"],
         "why": "影响不明显，多数保持观望", "risk": "观望态度，易被舆论带动"},
        {"role": "管理执行主体", "tagCls": "tag-amber", "att": "谨慎支持", "subj": subs["m"],
         "why": "有利于秩序与目标达成", "risk": "执行成本上升：" + c["cost"][0]},
        {"role": "潜在受损主体", "tagCls": "tag-violet", "att": "反对", "subj": subs["v"],
         "why": "感知成本增加或受益不均", "risk": "可能投诉、抵触与流失"},
        {"role": "高风险行为主体", "tagCls": "tag-red", "att": "倾向利用", "subj": subs["h"],
         "why": "寻求规则空间、钻规则空子的机会", "risk": "高危行为：" + c["vuln"][0]},
    ]
    out = []
    for r, d in zip(roles, dyn["groups"]):
        r = dict(r)
        r["appr"] = int(round(d["support"]))
        r["support"] = d["support"]
        r["riskVal"] = d["risk"]
        r["bar"] = role_map[d["key"]]
        r["riskMode"] = d["key"] == "h"
        out.append(r)
    return out


def deduce_chains(society_id, category_name, goal="提高满意度", scope="部分群体", strength="中等"):
    """双风险链：范围决定波及面节点、强度决定冲突节点、目标决定导向节点 → 链长与内容随属性变化。"""
    s, c = category_full(society_id, category_name)
    if c is None:
        return {"main": [], "alt": []}
    goal_node = {
        "提高效率": ["效率优先引发公平争议"],
        "增加收益": ["收益导向诱发套利"],
        "降低风险": ["风险控制趋于保守"],
        "提升公平": ["公平诉求挤压效率"],
        "提高满意度": ["满意度拉高预期"],
    }.get(goal, [])
    scope_node = {
        "小范围试点": ["试点范围受限，反馈价值高"],
        "部分群体": [],
        "全体推行": ["波及全体成员，舆情扩散"],
    }.get(scope, [])
    strength_node = {
        "温和": ["抵触情绪温和，易修正"],
        "中等": [],
        "严格": ["抵触升级为冲突"],
    }.get(strength, [])
    main = ["规则发布"] + goal_node + scope_node + list(c["chain"]) + strength_node + ["规则需要二次修改"]
    alt = ["规则发布"] + scope_node + list(c["alt"]) + strength_node + ["规则需要二次修改"]
    return {"main": main, "alt": alt}


def warn_vulnerabilities(society_id, category_name, content, strength="中等"):
    """漏洞预警：规则强度通过风险控制因子影响漏洞利用概率（严格降低、温和升高）。"""
    s, c = category_full(society_id, category_name)
    if c is None:
        return {"vulns": [], "audit": {"scanned": 0, "violations": []}}
    st = STRENGTH_FACTOR.get(strength, STRENGTH_FACTOR["中等"])
    prob_factor = 1.4 - st["riskControl"]  # 温和0.9 / 中等0.65 / 严格0.4
    vulns = []
    for i, v in enumerate(c["vuln"]):
        level = "高" if i < 2 else "中"
        base_prob = 0.55 if level == "高" else 0.30
        vulns.append({"name": v, "level": level,
                      "prob": int(round(base_prob * prob_factor * 100)),
                      "basis": "按规则强度「%s」的风险控制因子推算" % strength})
    cross = cross_terms(society_id)
    violations = [t for t in cross if any(t in v["name"] for v in vulns) and t not in content]
    return {"vulns": vulns, "audit": {"scanned": len(cross), "violations": violations}}


def cross_terms(society_id):
    import json
    s = kb.society(society_id)
    if s is None:
        return set()
    own_text = json.dumps(s, ensure_ascii=False)
    own_kw = {k for c in s["cats"] for k in c["kw"]}
    counter = {}
    for other in kb.SOC:
        for c in other["cats"]:
            for k in c["kw"]:
                counter[k] = counter.get(k, 0) + 1
    return {k for k, n in counter.items()
            if n == 1 and k not in own_kw and k not in own_text}


def generate_plans(society_id, category_name, metrics):
    """反事实方案：按发布目标权重 / 发布范围 / 规则强度计算方案评分 → 替代方案排序随属性变化。"""
    s, c = category_full(society_id, category_name)
    if c is None:
        return {"plans": [], "rec": None}
    goal = metrics.get("goal", "提高满意度")
    scope = metrics.get("scope", "部分群体")
    strength = metrics.get("strength", "中等")
    gw = GOAL_WEIGHTS.get(goal, GOAL_WEIGHTS["提高满意度"])
    risk = metrics.get("risk", 0)
    plans = [
        {"name": "原方案", "desc": "直接全面推行", "appr": "高", "risk": "高", "fair": "中", "diff": "低", "best": False},
        {"name": "温和方案", "desc": c["soft"], "appr": "中高", "risk": "低", "fair": "中高", "diff": "中", "best": False},
        {"name": "限制方案", "desc": c["lim"], "appr": "中", "risk": "低", "fair": "高", "diff": "中高", "best": False},
        {"name": "试点方案", "desc": "先在" + s["scope"] + "试点，收集反馈验证后推广", "appr": "中高", "risk": "中低", "fair": "高", "diff": "中", "best": False},
    ]
    score = {
        "原方案": 40 - risk * 0.2,
        "温和方案": 58 + (10 if strength == "温和" else 0) + gw["satisfaction"] * 6
                   - (10 if strength == "严格" else 0) + (4 if scope == "小范围试点" else 0),
        "限制方案": 58 + gw["riskControl"] * 10 + (10 if strength == "严格" else 0)
                   + (6 if goal == "降低风险" else 0),
        "试点方案": 60 + (18 if scope == "小范围试点" else -6 if scope == "全体推行" else 0)
                   + (10 if risk >= 55 else 0) + gw["fairness"] * 4,
    }
    for p in plans:
        p["score"] = round(score[p["name"]], 1)
    plans.sort(key=lambda p: -p["score"])
    best_name = plans[0]["name"]
    for p in plans:
        p["best"] = (p["name"] == best_name)
    rec_plan = best_name
    subs = _subjects(s, c)
    why = {
        "试点方案": "虽然推进速度较慢，但能够在「" + s["scope"] + "」先验证本场景的核心风险（" + c["risk"][0] + "），并保留根据反馈修正的空间。",
        "限制方案": "能够直接封堵「" + c["vuln"][0] + "」这一高等级漏洞，在不牺牲推行速度的前提下把风险控制在可接受范围。",
        "温和方案": "以较小幅度渐进推行，给潜在受损主体（" + subs["v"] + "）留出适应时间，降低反对度与执行阻力。",
        "原方案": "推进最快，但按当前风险指数（" + str(risk) + "/100）不宜直接全面推行。",
    }[rec_plan]
    return {"plans": plans, "rec": {"name": rec_plan, "desc": rec_desc(s, c, rec_plan), "why": why}}


def conclusion(society_id, category_name, content, ident, metrics):
    s, c = category_full(society_id, category_name)
    subs = _subjects(s, c)
    vuln0 = c["vuln"][0]
    return ('系统识别场景：<b>%s · %s</b>（后端 MCP 流水线推演）。在虚拟社会中针对“<b>%s</b>”的推演显示：'
            '该发布内容<b>具有一定可行性</b>，预计总体赞成度较高（<b>%d%%</b>），但存在<b>「%s」</b>等规则漏洞与'
            '<b>潜在受损主体</b>（%s）受益不均的风险（风险指数 <b>%d/100</b>）。建议采用<b>「%s」</b>：%s，并设置限制条件和反馈机制。'
            ) % (s["name"], c["name"], _esc(content), metrics["approve"], vuln0, subs["v"], metrics["risk"],
                 metrics["recPlan"], rec_desc(s, c, metrics["recPlan"]))


def build_report(society_id, category_name, content, ident, metrics, chains, vulns, audit, plans, rec,
                 data_source, conclusion_html, run_index, validation, trace, llm_mode, goal, scope, strength):
    import datetime
    s, c = category_full(society_id, category_name)
    subs = _subjects(s, c)
    date_str = datetime.date.today().strftime("%Y-%m-%d")
    inferred = ident.get("inferred", False)
    matched_kw = ident.get("matched_kw")
    conf = ("推断模式（<b>以下为基于当前社会类型的推断</b>：输入未命中关键词，按「%s」推断）" % c["name"]) if inferred \
        else ("高置信模式（关键词「%s」命中「%s」）" % (matched_kw, c["name"]))
    src = data_source or "系统内置模拟参数（基于「%s · %s」主体画像仿真生成）" % (s["name"], c["name"])
    ab = attribute_basis(goal, scope, strength)
    plan_list = [("原方案", "直接全面推行"), ("温和方案", c["soft"]), ("限制方案", c["lim"]),
                 ("试点方案", "先在" + s["scope"] + "试点，验证后推广")]
    v_checks = "；".join("%s：%s" % (ck["name"], "通过" if ck["passed"] else "未通过") for ck in validation["checks"])
    t_checks = "；".join("%s@%s（%s，%d ms，重试 %d 次）" % (t["tool"], t["server"], t["status"], t.get("ms", 0), t.get("retries", 0)) for t in trace)
    secs = [
        {"t": "一、发布内容概述", "html": "<p>本次试运行的分析对象为：<b>“%s”</b>。规则属性设定为：发布目标「%s」、发布范围「%s」、规则强度「%s」。识别置信方式：%s。本会话累计完成 <b>第 %d 次试运行</b>。</p>"
         "<p><b>本结果受以下规则属性影响：</b><br>发布目标「%s」：%s<br>发布范围「%s」：%s<br>规则强度「%s」：%s</p>"
         "<p>核心推演参数：综合支持度 <b>%s</b>、综合风险值 <b>%s</b>、受影响人数约 <b>%s</b> 人（范围因子 %s × 群体相关系数 %s，基准人口 %s）。</p>"
         % (_esc(content), _esc(goal), _esc(scope), _esc(strength), conf, run_index,
            ab["goal"], ab["goal_effect"], ab["scope"], ab["scope_effect"], ab["strength"], ab["strength_effect"],
            metrics["composite"]["support"], metrics["composite"]["risk"],
            "{:,}".format(metrics["composite"]["affected"]),
            metrics["composite"]["scope_factor"], metrics["composite"]["correlation"],
            "{:,}".format(metrics["composite"]["total_pop"]))},
        {"t": "二、虚拟社会类型与规则类别", "html": "<p>本次推演选用的虚拟社会类型为<b>「%s %s」</b>，识别到的规则类别为<b>「%s」</b>（涵盖：%s）。分析全部使用本场景专属词语，未混入其他场景内容。</p>"
         '<div class="r-kv"><div class="kv"><div class="k">直接受影响主体</div><div class="v">%s</div></div>'
         '<div class="kv"><div class="k">间接受影响主体</div><div class="v">%s</div></div>'
         '<div class="kv"><div class="k">管理执行主体</div><div class="v">%s</div></div>'
         '<div class="kv"><div class="k">潜在受损主体</div><div class="v">%s</div></div>'
         '<div class="kv"><div class="k">高风险行为主体</div><div class="v">%s</div></div>'
         '<div class="kv"><div class="k">主要群体</div><div class="v">%s</div></div></div>'
         % (s["ico"], s["name"], c["name"], c["desc"], subs["d"], subs["i"], subs["m"], subs["v"], subs["h"], s["groups"])},
        {"t": "三、数据来源", "html": "<p>本次推演使用的数据来源为：<b>%s</b>；公开数据（%s）用于校准主体规模与行为基线。问卷统计按参数转换表映射为初始赞成度、成本感知、公平风险、漏洞风险与行为变化概率等推演参数。</p>"
         % (_esc(src), s["data"])},
        {"t": "四、主体反应（五类角色）", "html": "<p>推演显示五类主体对同一规则的反应存在显著差异：</p><ul>"
         "<li><b>支持与观望</b>：直接受影响主体（%s）预期受益，赞成度约 72%%；间接受影响主体（%s）态度中立（约 54%%），短期以观望为主。</li>"
         "<li><b>反对与投诉</b>：潜在受损主体（%s）感知成本增加或受益不均，赞成度仅约 24%%，是投诉与抵触的主要来源。</li>"
         "<li><b>管理行为</b>：管理执行主体（%s）谨慎支持，但担心「%s」，执行成本上升。</li>"
         "<li><b>高风险行为</b>：高风险行为主体（%s）倾向利用规则空间，预计最可能尝试「%s」。</li></ul>"
         % (subs["d"], subs["i"], subs["v"], subs["m"], c["cost"][0], subs["h"], c["vuln"][0])},
        {"t": "五、风险链分析（主链 + 备选链）", "html": "<p><b>主风险链：</b>%s。</p><p><b>备选风险链：</b>%s。</p>"
         "<p>两条链条表明：风险并不来自规则本身，而来自<b>主体行为的相互挤压与连锁传导</b>。在链条中段节点插入干预，即可显著阻断风险扩散。</p>"
         % (" → ".join(chains["main"]), " → ".join(chains["alt"]))},
        {"t": "六、漏洞预警", "html": "<p>系统识别出该规则在「%s」场景下可能被利用、误解或规避的位置：</p><ul>%s</ul>"
         "<p>漏洞利用概率随规则强度变化（严格降低、温和升高）；以上漏洞均来自本场景专属知识库，与「%s」严格一致（跨场景串词扫描 %d 个外来词，命中 %d 个）。</p>"
         % (c["name"], "".join("<li><b>%s</b>（预警等级：%s，利用概率约 %d%%）</li>" % (v["name"], v["level"], v.get("prob", 0)) for v in vulns),
            s["name"], audit.get("scanned", 0), len(audit.get("violations", [])))},
        {"t": "七、替代方案对比", "html": "<p>系统生成 4 个反事实方案并与原方案对比：</p><ul>%s</ul>"
         "<p>综合推演指标（风险指数 %d/100，漏洞风险%s），系统推荐采用<b>「%s」</b>（%s）。推荐理由：%s</p>"
         % ("".join("<li><b>%s</b>：%s</li>" % (p[0], p[1]) for p in plan_list),
            metrics["risk"], metrics["hole"], rec["name"], rec["desc"], rec["why"])},
        {"t": "八、最终建议", "html": "<ul>"
         "<li><b>是否适合发布</b>：有条件适合。总体赞成度 %d%%、公平性 %d/100 表明具备发布基础，但风险指数 %d/100 提示不宜按原方案直接全面推行。</li>"
         "<li><b>如何修改</b>：重点修补「%s」与「%s」两类高等级漏洞，可参考限制方案（%s）。</li>"
         "<li><b>是否需要试点</b>：%s</li>"
         "<li><b>是否需要补偿机制</b>：建议为潜在受损主体（%s）设置过渡性补偿、豁免或辅助条款，降低公平性风险。</li>"
         "<li><b>反馈机制</b>：设置试点反馈窗口，收集结构化意见并回流至沙盒，迭代验证后再扩大范围。</li></ul>"
         % (metrics["approve"], metrics["fairness"], metrics["risk"],
            c["vuln"][0], c["vuln"][1], c["lim"],
            ("<b>需要</b>。先在" + s["scope"] + "试点，重点监测「" + c["risk"][0] + "」与投诉量两个先行指标。") if metrics["recPlan"] == "试点方案"
            else ("可结合「" + metrics["recPlan"] + "」先行验证，再决定扩大范围。"),
            subs["v"])},
        {"t": "九、系统校验与执行轨迹", "html": "<p>本次分析经规则校验器逐项核验：<b>%s</b>。LLM 网关模式：<b>%s</b>。</p>"
         "<p style=\"font-size:12.5px;color:var(--muted)\">MCP 调用轨迹：%s</p>"
         % (v_checks, llm_mode, t_checks)},
    ]
    head = ("<div class=\"report-head\"><div class=\"rh-tag\">RULE SANDBOX PRO · MCP PIPELINE · EXPLAINABLE REPORT</div>"
            "<h2>规则试运行分析报告</h2>"
            "<div class=\"rh-meta\"><span>虚拟社会：%s %s</span><span>规则类别：%s</span><span>风险指数：%d/100</span>"
            "<span>推荐策略：%s</span><span>%s</span><span>会话第 %d 次运行</span><span>校验器：%d/%d 通过</span><span>%s</span></div></div>"
            % (s["ico"], s["name"], c["name"], metrics["risk"], metrics["recPlan"],
               "推断模式" if inferred else "高置信识别", run_index,
               sum(1 for ck in validation["checks"] if ck["passed"]), len(validation["checks"]), date_str))
    body = "<div class=\"report-body\">%s</div>" % "".join(
        "<div class=\"r-sec\"><div class=\"r-sec-title\"><span class=\"r-no\">%d</span>%s</div>%s</div>"
        % (i + 1, x["t"], x["html"]) for i, x in enumerate(secs))
    return {"head": head, "sections": secs, "html": head + body, "conclusion": conclusion_html, "date": date_str}
