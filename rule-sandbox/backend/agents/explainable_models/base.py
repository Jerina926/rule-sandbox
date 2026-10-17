"""5 个可解释推演模型的统一基类。

每个模型的输出结构：

  {
    "model_name": str,                # 模型英文 id
    "title": str,                     # 中文展示名（答辩用）
    "description": str,               # 一句话用途说明
    "result": dict,                   # 主结果（与现有 analysis 字段兼容）
    "computation_basis": [str],       # 计算依据：每一步用了什么公式/数据
    "factor_breakdown": [             # 影响因素：每个影响因素的 name/weight/direction/evidence
      {"name": str, "weight": float, "direction": "support"|"neutral"|"against",
       "evidence": str, "raw_value": Any},
      ...
    ],
    "formula": str,                   # LaTeX-like 公式描述
    "evidence_refs": [str],           # 引用公开数据源（用于挑战杯可信度）
    "confidence": float,              # 0~1
    "processing_ms": int,             # 实际耗时（毫秒）
  }
"""
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Factor:
    name: str
    weight: float                 # 0.0 ~ 1.0
    direction: str                # "support" | "neutral" | "against"
    evidence: str = ""
    raw_value: Any = None

    def as_dict(self):
        return {"name": self.name, "weight": round(self.weight, 3),
                "direction": self.direction, "evidence": self.evidence,
                "raw_value": self.raw_value}


@dataclass
class ModelOutput:
    model_name: str
    title: str
    description: str
    result: dict = field(default_factory=dict)
    computation_basis: list = field(default_factory=list)
    factor_breakdown: list = field(default_factory=list)
    formula: str = ""
    evidence_refs: list = field(default_factory=list)
    confidence: float = 1.0
    processing_ms: int = 0

    def as_dict(self):
        return {
            "model_name": self.model_name,
            "title": self.title,
            "description": self.description,
            "result": self.result,
            "computation_basis": self.computation_basis,
            "factor_breakdown": [f if isinstance(f, dict) else f.as_dict() for f in self.factor_breakdown],
            "formula": self.formula,
            "evidence_refs": self.evidence_refs,
            "confidence": round(self.confidence, 3),
            "processing_ms": self.processing_ms,
        }


def _now_ms():
    import time
    return int(time.time() * 1000)


def _consume(start_ms):
    import time
    return int(time.time() * 1000) - start_ms


# 用于答辩展示：模型元数据（名称、用途、公式）
CATALOG = [
    {
        "id": "scene_detection",
        "title": "场景识别",
        "purpose": "从 8 类社会 × 44 个规则类别中，自动识别用户输入属于哪个细分类别，并给出置信度与方向（放宽/收紧/取消/新增）。",
        "stage": "上线前 0~60 秒",
        "output": "{society, category, direction, matched_kw, confidence}",
    },
    {
        "id": "cohort_profile",
        "title": "群体画像",
        "purpose": "把社会成员分成 5 类主体（直接/间接/管理/潜在受损/高风险行为），逐类估算基线支持度，并解释为什么这些人会支持/反对。",
        "stage": "上线前 1~2 分钟",
        "output": "[{role, att, appr, why, risk}, ×5]",
    },
    {
        "id": "support_calculation",
        "title": "支持度计算",
        "purpose": "基于「推行范围 × 推行强度」二维矩阵，计算总体支持度 / 反对度 / 风险指数 / 公平性，并确定推荐方案。",
        "stage": "上线前即时",
        "output": "{approve, oppose, risk, fairness, recPlan, diff, hole}",
    },
    {
        "id": "risk_chain",
        "title": "风险链生成",
        "purpose": "按时间顺序串联主风险链与备选风险链，量化每节点的潜在影响人数、时滞、可逆性、风险等级。",
        "stage": "上线前 2~3 分钟",
        "output": "{main: [step...], alt: [step...], impact_index}",
    },
    {
        "id": "alternative_compare",
        "title": "替代方案比较",
        "purpose": "对原/温和/限制/试点 4 个方案做多目标加权打分（支持·风险·公平·难度），给出推荐方案与建议调整方向。",
        "stage": "上线前即时",
        "output": "{rank: [{name, score, vector}], recommended, trade_off}",
    },
]
