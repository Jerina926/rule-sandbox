"""模型 3/5：支持度计算（Support Calculation）

输入：goal, scope, strength（baseline 参数仅为兼容旧签名保留，不参与计算）
输出：{approve, oppose, risk, fairness, recPlan, diff, hole}

算法：直接调用 knowledge.engine.simulate_metrics —— 与 /api/analyze 主推演管线严格共用同一套公式：
  群体维度 group_dynamics：
    支持度_i = 基础支持度 + 目标匹配度 − 强度抵触度 − 范围公平损失
    风险值_i  = 基础风险 × scopeFactor × strengthRiskFactor × 群体脆弱性
  综合维度：Σ(值 × 人数权重) / Σ人数权重，经目标风险系数与目标人口加成后得到最终指标，
  再按阈值映射 diff / hole / recPlan。
"""
from knowledge import engine as kn_engine
from .base import ModelOutput, Factor, _now_ms, _consume

SCOPE_KEYS = ("小范围试点", "部分群体", "全体推行")
STRENGTH_KEYS = ("温和", "中等", "严格")

# 置信度为「先验数据可信度标注」：由输入数据来源类型导出（非统计置信区间）
_SOURCE_CONF = {"live": 0.85, "public": 0.72, "simulated": 0.58}


def run(scope="部分群体", strength="中等", baseline=None, goal="提高满意度", data_source=""):
    t0 = _now_ms()
    if scope not in SCOPE_KEYS:
        scope = "部分群体"
    if strength not in STRENGTH_KEYS:
        strength = "中等"

    m = kn_engine.simulate_metrics(goal, scope, strength, data_source=data_source or "")
    attrs = m["attributes"]

    factors = [
        Factor(name="发布目标：" + m["goal"], weight=0.4, direction="neutral",
               evidence=("目标权重：效率 %.2f / 收益 %.2f / 满意度 %.2f / 公平 %.2f / 风险控制 %.2f"
                         % (attrs["goal_weights"]["efficiency"], attrs["goal_weights"]["benefit"],
                            attrs["goal_weights"]["satisfaction"], attrs["goal_weights"]["fairness"],
                            attrs["goal_weights"]["riskControl"])),
               raw_value=attrs["goal_weights"]),
        Factor(name="发布范围：" + m["scope"], weight=0.3,
               direction=("against" if m["scope"] == "全体推行" else "support"),
               evidence=("范围因子 %.2f：直接缩放受影响人数、风险暴露、总收益与总成本，并影响公平感知"
                         % attrs["scope_factor"]),
               raw_value={"scope_factor": attrs["scope_factor"]}),
        Factor(name="规则强度：" + m["strength"], weight=0.3,
               direction=("against" if m["strength"] == "严格" else "support"),
               evidence=("执行 %.2f / 抵触 %.2f / 风险控制 %.2f / 遵守率 %.2f"
                         % (attrs["strength_factor"]["execution"], attrs["strength_factor"]["resistance"],
                            attrs["strength_factor"]["riskControl"], attrs["strength_factor"]["compliance"])),
               raw_value=attrs["strength_factor"]),
    ]

    conf_kind = ("live" if (m["live"] or {}).get("used")
                 else ("public" if (m["data_source"] and m["data_source"] != "系统内置模拟参数")
                       else "simulated"))
    confidence = _SOURCE_CONF[conf_kind]

    basis = [
        "输入：发布目标=%s / 发布范围=%s / 规则强度=%s（非法值由主引擎规整为合法档位）"
        % (m["goal"], m["scope"], m["strength"]),
        "与 /api/analyze 主推演管线共用 knowledge.engine.simulate_metrics，结果逐字段一致",
        ("群体维度 group_dynamics：支持度_i = 基础支持度 + 目标匹配度 − 强度抵触度 − 范围公平损失；"
         "风险值_i = 基础风险 × scopeFactor(%.2f) × strengthRiskFactor(%.2f) × 群体脆弱性"
         % (attrs["scope_factor"], attrs["strength_risk_factor"])),
        ("综合支持度 = Σ(支持度_i×人数权重)/Σ权重 = %s；综合风险 = Σ(风险值_i×人数权重)/Σ权重 × 目标风险系数 = %s"
         % (m["composite"]["support"], m["composite"]["risk"])),
        ("汇总指标（已 clamp）：approve=%d，oppose=%d，risk=%d，fairness=%d，benefit=%d，cost=%d，"
         "behavior=%d，diffNum=%d"
         % (m["approve"], m["oppose"], m["risk"], m["fairness"], m["benefit"], m["cost"],
            m["behavior"], m["diffNum"])),
        "分级阈值（与主引擎一致）：diff=偏高(diffNum≥62)/较低(<38)/中等；hole=偏高(risk≥50)/中等(≥35)/较低；"
        "recPlan=试点方案(risk≥55)/限制方案(≥35)/温和方案",
        "数据来源：%s —— %s" % (m["data_source"], m["source_basis"]),
        ("confidence=%.2f：由数据来源类型导出的先验数据可信度标注"
         "（实时公开数据 0.85 / 公开数据校准 0.72 / 内置模拟参数 0.58），非统计置信区间" % confidence),
    ]

    return ModelOutput(
        model_name="support_calculation", title="支持度计算",
        description="直接调用主推演引擎，按「发布目标 × 发布范围 × 规则强度」计算总体支持度 / 反对度 / 风险指数 / 公平性，并依阈值推荐方案。",
        result={"approve": int(m["approve"]), "oppose": int(m["oppose"]),
                "risk": int(m["risk"]), "fairness": int(m["fairness"]),
                "diff": m["diff"], "hole": m["hole"], "recPlan": m["recPlan"],
                "goal": m["goal"], "scope": m["scope"], "strength": m["strength"],
                "data_source": m["data_source"], "source_basis": m["source_basis"],
                "composite": m["composite"],
                "steps": [{"stage": "simulate_metrics", "params": attrs,
                           "composite": m["composite"]}]},
        computation_basis=basis,
        factor_breakdown=factors,
        formula=("support_i = 基础支持度 + 目标匹配度 − 强度抵触度 − 范围公平损失 ; "
                 "risk_i = 基础风险 × scopeFactor × strengthRiskFactor × 脆弱性 ; "
                 "综合支持度 = Σ(support_i×w_i)/Σw_i ; 综合风险 = Σ(risk_i×w_i)/Σw_i × 目标风险系数 ; "
                 "approve = clamp(综合支持度 + 目标人口加成, 20, 92) ; diff/hole/recPlan 按分级阈值映射"),
        evidence_refs=[{"name": "国家统计局 · 官方统计发布渠道",
                         "url": "https://www.stats.gov.cn/",
                         "use": "选择公开数据来源时的官方发布方标注参照"},
                        {"name": "北京大学中国社会科学调查中心 (CGSS)",
                         "url": "https://cgss.ruc.edu.cn/",
                         "use": "社会公众政策态度 / 公平感知类基线研究的领域参照"}],
        confidence=confidence,
        processing_ms=_consume(t0)).as_dict()