"""模型 1/5：场景识别（Scene Detection）

输入：society_id, content
输出：{society, category, direction, matched_kw, is_inferred, confidence, score, runner_up}

算法（与 knowledge.engine.detect 完全一致但带有完整的解释）：
  score(content, c) = Σ_{k∈c.kw} 1[k ∈ content]
  本社会内取 score 最高的类别作为 best_cat；
  其他社会若命中 ≥2 关键词 → 触发「跨社会警报」（mismatch）；
  若本社会完全无命中 → inferred = True（按 cats[0] 推断）；
  方向识别：放宽 / 收紧 / 取消 / 新增 / 调整。
"""
from knowledge import kb
from knowledge import engine as kn_engine
from .base import ModelOutput, Factor, _now_ms, _consume

DIRECTION_RULES = kn_engine.DIRECTIONS


def detect_direction(content):
    for keys, label in DIRECTION_RULES:
        hit = [k for k in keys if k in content]
        if hit:
            return label, hit
    return "调整", []


def _kw_count(society, content):
    return sum(1 for c in society["cats"] for k in c["kw"] if k in content)


def run(society_id, content, force=False):
    """主入口：返回一个完整可解释的 ModelOutput。"""
    t0 = _now_ms()
    cur = kb.society(society_id)
    if cur is None:
        return ModelOutput(
            model_name="scene_detection", title="场景识别",
            description="从 8 类社会 × 44 个规则类别中识别当前输入所属细分类别。",
            result={"society_id": society_id, "status": "error", "message": "未知社会类型"},
            computation_basis=[f"society_id={society_id} 不在 8 类社会知识库中"],
            confidence=0.0, processing_ms=_consume(t0)).as_dict()

    # 1) 计算本社会每个类别的关键词命中分
    scores = []
    for c in cur["cats"]:
        hits = [k for k in c["kw"] if k in content]
        scores.append({"category_name": c["name"], "kw": c["kw"],
                       "hit_count": len(hits), "hit_keywords": hits,
                       "score": round(len(hits) / max(1, len(c["kw"])), 3),
                       "ratio_denominator": "max(len(category.kw), 1)"})
    scores.sort(key=lambda x: (-x["hit_count"], -x["score"]))

    best = scores[0] if scores else None
    runner_up = scores[1] if len(scores) > 1 else None

    # 2) 跨社会扫描
    other = None
    for s in kb.SOC:
        if s["id"] == society_id:
            continue
        for c in s["cats"]:
            hits = [k for k in c["kw"] if k in content]
            if hits and (other is None or _kw_count(s, content) > other["count"]):
                other = {"society_name": s["name"], "ico": s["ico"],
                         "category_name": c["name"], "kw": hits, "count": len(hits)}
                break

    # 3) 决策
    inferred = (best is None) or (best["hit_count"] == 0)
    mismatch = (best is None or best["hit_count"] == 0) and other and other["count"] >= 2 and not force

    if mismatch:
        status = "mismatch"
        best_cat = None
        confidence = 0.0
    elif inferred and not force:
        status = "ok"
        best_cat = cur["cats"][0] if cur["cats"] else None
        confidence = 0.55  # 推断默认置信度偏低
    else:
        status = "ok"
        best_cat = _cat_by_name(cur, best["category_name"])
        # 置信度与命中数成正比
        confidence = min(0.98, 0.55 + best["hit_count"] * 0.15 + (0.05 if (best_cat and len(best["hit_keywords"]) >= 2) else 0))

    direction, dir_hits = detect_direction(content)

    # 4) 组装计算依据
    basis = []
    basis.append(f"输入社会类型：{cur['name']}（含 {len(cur['cats'])} 个内置规则类别，每类平均 {sum(len(c['kw']) for c in cur['cats']) / max(1, len(cur['cats'])):.1f} 个识别关键词）")
    basis.append(f"输入内容：「{content}」（字符数 {len(content)}）")
    for i, s in enumerate(scores[:3]):
        marker = "★" if i == 0 and not inferred else (" " if s["hit_count"] > 0 else "·")
        kw_str = "、".join(s["hit_keywords"]) if s["hit_keywords"] else "（无命中）"
        basis.append(f"{marker} {cur['name']} · {s['category_name']}: 命中 {s['hit_count']}/{len(s['kw'])} 个关键词 [{kw_str}]")
    if other:
        basis.append(f"⚠ 跨社会扫描：「{other['society_name']} · {other['category_name']}」命中 {other['count']} 个关键词 {other['kw']} → {'mismatch 拦截' if mismatch else '告警但按当前社会处理'}")
    basis.append(f"方向识别：{direction}（命中方向词 {dir_hits}）")
    basis.append(f"置信度计算：base 0.55 + 命中关键词数 × 0.15，最大 0.98 → 实测 {confidence:.2f}")

    # 5) 影响因素（每个候选类别一个 Factor）
    factors = []
    for s in scores[:5]:
        if s["hit_count"] == 0:
            fdir = "neutral"
        else:
            fdir = "support"
        factors.append(Factor(
            name=f"{cur['name']} · {s['category_name']}",
            weight=round(s["score"], 3),
            direction=fdir,
            evidence=f"命中关键词 {s['hit_keywords']}（{s['hit_count']}/{len(s['kw'])}，覆盖率 {s['score']*100:.0f}%）",
            raw_value=s["hit_count"]))

    # 6) 公开数据源（用于挑战杯可信度）
    evidence_refs = []
    # cur["data"] 是字符串（"学校通知、图书馆使用记录…"），不是 dict
    data_text = cur.get("data", "")
    if isinstance(data_text, str) and data_text:
        evidence_refs.append({"name": data_text, "url": "",
                              "use": "本社会类型常用的官方数据来源类别（关键词命中率/规则类别的数据基础）"})

    return ModelOutput(
        model_name="scene_detection", title="场景识别",
        description="从 8 类社会 × 44 个规则类别中识别当前输入所属细分类别，并量化跨社会串词风险。",
        result={"status": status, "society_name": cur["name"], "ico": cur["ico"],
                "category_name": best["category_name"] if best else None,
                "matched_kw": best["hit_keywords"] if best else [],
                "is_inferred": inferred, "direction": direction,
                "confidence": round(confidence, 3),
                "runner_up": runner_up["category_name"] if runner_up else None,
                "cross_society_warning": other,
                "scores": scores[:5]},
        computation_basis=basis,
        factor_breakdown=factors,
        formula=("score(content, c) = Σ 1[k ∈ content] for k ∈ c.kw ; "
                 "best = argmax(score) ; "
                 "confidence = clamp(0.55 + hit_count·0.15, 0, 0.98) ; "
                 "inferred = (best is None or best.hit_count==0)"),
        evidence_refs=evidence_refs,
        confidence=round(confidence, 3),
        processing_ms=_consume(t0)).as_dict()


def _cat_by_name(society, name):
    for c in society["cats"]:
        if c["name"] == name:
            return c
    return None
