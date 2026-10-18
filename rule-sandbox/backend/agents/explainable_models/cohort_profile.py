"""模型 2/5：群体画像（Cohort Profile）

输入：society, category, benefits, costs, risks
输出：5 类主体的画像（角色 / 态度 / 支持度 / 风险行为 / 解释）

分类（已与 knowledge.engine.deduce_groups 对齐）：
  d = 直接受影响主体（关联程度最强）
  i = 间接受影响主体（信息不对称导致观望）
  m = 管理执行主体（落实规则）
  v = 潜在受损主体（受益不均 / 需补偿机制）
  h = 高风险行为主体（钻规则空子倾向）

支持度模型：
  appr_s = clamp(60 + role_offset(d/i/m/v/h) + 1.5·matched_benefit − 2.0·matched_cost + delta_inferred, 8, 92)
  其中：role_offset ∈ {+12, −6, +1, −36, +22}
        matched_benefit = 该主体的描述与收益列表的关键词重合数
        matched_cost    = 与成本列表的关键词重合数
        delta_inferred  = 若该识别为推断，主体支持度额外 ±0（只影响不确定性）
"""
from knowledge import kb
from .base import ModelOutput, Factor, _now_ms, _consume


ROLE_OFFSETS = {"d": +12, "i": -6, "m": +1, "v": -36, "h": +22}
ROLE_LABELS = {"d": "直接受影响主体", "i": "间接受影响主体", "m": "管理执行主体",
               "v": "潜在受损主体",    "h": "高风险行为主体"}
ROLE_TAGS = {"d": "tag-green", "i": "tag-blue", "m": "tag-amber", "v": "tag-violet", "h": "tag-red"}
ROLE_BARS = {"d": "fb-green",  "i": "fb-blue",  "m": "fb-amber",  "v": "fb-violet",  "h": "fb-red"}
ROLE_ATT = {"d": "支持偏中立", "i": "中立",      "m": "谨慎支持",  "v": "反对",        "h": "倾向利用"}
RISK_MODE = {"d": False,         "i": False,      "m": False,      "v": False,        "h": True}


def _kw_overlap(text, kw_list):
    return sum(1 for k in kw_list if k in text)


def run(society_id, category_name):
    t0 = _now_ms()
    s, c = (None, None)
    if society_id:
        s = kb.society(society_id)
    if s is not None and category_name:
        for x in s["cats"]:
            if x["name"] == category_name:
                c = x
                break
    if s is None or c is None:
        return ModelOutput(
            model_name="cohort_profile", title="群体画像",
            description="把社会成员分成 5 类主体，逐类估算基线支持度。",
            result={"groups": []}, confidence=0.0,
            computation_basis=[f"未找到社会={society_id} 或类别={category_name} 的知识条目"],
            processing_ms=_consume(t0)).as_dict()

    subs = dict(s["subj"]); subs.update(c.get("subs") or {})
    benchmark = {"d": 60, "i": 54, "m": 61, "v": 24, "h": 82}  # 用于解释的参照
    groups = []
    factors = []

    for role in ["d", "i", "m", "v", "h"]:
        subj = subs[role]
        # 计算该主体描述与该类别收益/成本的关键词重合
        mb = _kw_overlap(subj, c.get("benefit", []))
        mc = _kw_overlap(subj, c.get("cost", []))
        raw = 60 + ROLE_OFFSETS[role] + 1.5 * mb - 2.0 * mc
        appr = max(8, min(92, int(round(raw))))
        # 解释字符串
        if role == "d":
            why = (f"「{subj}」是该规则的直接关联方，因受益项「{c['benefit'][0]}」"
                   f"可达成而倾向支持；同时因成本「{c['cost'][0]}」存在保留意见")
            risk_reason = f"配合度会随执行细节波动；首要顾虑是「{c['cost'][0]}」"
        elif role == "i":
            why = (f"「{subj}」对该规则无直接相关影响，信息不对称使其多数保持观望；"
                   f"易被舆论带动形成「沉默的多数」")
            risk_reason = "易被舆论裹挟，态度两极化"
        elif role == "m":
            why = (f"「{subj}」承担本规则的落地执行，认为长期对秩序与目标达成有利")
            risk_reason = f"执行成本增加：{c['cost'][0]}；可能引发一线人员消极应付"
        elif role == "v":
            why = (f"「{subj}」可能感知相对成本或受益不均，是潜在受损群体，倾向反对")
            risk_reason = "可能投诉、抵触甚至流失，需要补偿机制"
        else:  # h
            why = (f"「{subj}」倾向寻找规则中的空子与灰色地带，"
                   f"对漏洞「{c['vuln'][0]}」存在主观利用动机")
            risk_reason = f"高危行为触发源：「{c['vuln'][0]}」"

        groups.append({"role_key": role, "role": ROLE_LABELS[role], "tagCls": ROLE_TAGS[role],
                       "bar": ROLE_BARS[role], "att": ROLE_ATT[role], "subj": subj,
                       "appr": appr, "appr_delta": appr - benchmark[role],
                       "appr_raw_formula": f"60 + ({ROLE_OFFSETS[role]}) + 1.5·{mb} − 2.0·{mc} = {raw:.1f} → clamp {appr}",
                       "why": why, "risk": risk_reason, "riskMode": RISK_MODE[role],
                       "matched_benefit": mb, "matched_cost": mc})

        factors.append(Factor(
            name=ROLE_LABELS[role] + "（" + subj + "）",
            weight=round(ROLE_OFFSETS[role] / 36 + 0.5, 3),  # 归一到 0~1
            direction=("support" if appr >= 55 else "neutral" if appr >= 40 else "against"),
            evidence=(f"主体描述与 {len(c.get('benefit',[]))} 条收益中 {mb} 项命中；"
                      f"与 {len(c.get('cost',[]))} 条成本中 {mc} 项命中"),
            raw_value={"appr": appr, "raw": round(raw, 1),
                       "matched_benefit": mb, "matched_cost": mc}))

    # 计算依据
    basis = []
    basis.append(f"社会 = {s['name']}，类别 = {c['name']}；本类知识库内置 {len(c.get('benefit',[]))} 条收益、{len(c.get('cost',[]))} 条成本、{len(c.get('risk',[]))} 条风险、{len(c.get('vuln',[]))} 条漏洞")
    basis.append("5 类主体分类参考：管理学 + 行为经济学 + 政策评估领域的「利益相关者分析」(Freeman 1984) 与「政策遵从者画像」(Schneider & Ingram 1993)")
    for g in groups:
        basis.append(f"· {g['role']}（{g['subj']}）：{g['appr_raw_formula']}")
    basis.append("上述 5 类支持度的算术平均即作为总体画像的代表性观察（≠支持度计算的总体值，避免重复计算）")
    avg = round(sum(g["appr"] for g in groups) / len(groups), 1)
    basis.append(f"5 类支持度算术平均 = {avg}（参考画像基线）")

    # 置信度由影响因子覆盖度导出（先验数据可信度标注，非统计置信区间）
    total_overlaps = sum(g["matched_benefit"] + g["matched_cost"] for g in groups)
    confidence = round(min(0.92, 0.55 + 0.05 * total_overlaps), 2)
    basis.append(f"confidence={confidence}：由影响因子覆盖度导出（5 类主体与收益/成本关键词重合总数 = "
                 f"{total_overlaps}，公式 min(0.92, 0.55 + 0.05×重合数)），为内部可解释性标注，非统计置信区间")

    return ModelOutput(
        model_name="cohort_profile", title="群体画像",
        description="把社会成员分成 5 类主体，逐类用基线 + 角色偏移 + 收益/成本匹配量化支持度，并解释每类主体的态度成因。",
        result={"groups": groups, "avg_image_baseline": avg,
                "subject_groups": {"d": subs["d"], "i": subs["i"], "m": subs["m"], "v": subs["v"], "h": subs["h"]}},
        computation_basis=basis,
        factor_breakdown=factors,
        formula=("appr_s = clamp(60 + role_offset[s] + 1.5·matched_benefit − 2.0·matched_cost, 8, 92) ; "
                 "role_offset = {d:+12, i:-6, m:+1, v:-36, h:+22}"),
        evidence_refs=[{"name": "Freeman 1984 · Strategic Management: A Stakeholder Approach",
                         "url": "https://www.britannica.com/biography/R-Edward-Freeman",
                         "use": "5 类利益相关者划分法"},
                        {"name": "Schneider & Ingram 1993 · Policy Targeting and Social Construction",
                         "url": "https://www.jstor.org/stable/2132729",
                         "use": "政策遵从者画像理论"}],
        confidence=confidence,
        processing_ms=_consume(t0)).as_dict()
