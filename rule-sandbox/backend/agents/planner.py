import time

from knowledge import engine
from knowledge import public_fetch

SERVERS = {
    "identify": ("society-identification", "identify"),
    "questionnaire": ("society-identification", "build_questionnaire"),
    "metrics": ("risk-chain", "simulate_metrics"),
    "groups": ("risk-chain", "deduce_groups"),
    "chains": ("risk-chain", "deduce_chains"),
    "vulns": ("vulnerability-warning", "warn_vulnerabilities"),
    "plans": ("plan-generation", "generate_plans"),
}

LLM_SYSTEM = (
    "你是规则沙盒系统的分析总结专家。根据给定的推演数据，用中文写一段 3-4 句的总体结论，"
    "要求：先说明场景识别结果，再说明赞成度与风险，最后给出推行建议。只输出结论正文，不要标题。"
    "结论中将出现的关键词语必须来自给定的数据，禁止引入其他场景的词语。")


class Planner:
    def __init__(self, manager, gateway, validator):
        self.manager = manager
        self.gateway = gateway
        self.validator = validator

    async def _call(self, step_name, args, local_fn, trace):
        server, tool = SERVERS[step_name]
        t0 = time.time()
        payload, retries, err = await self.manager.call_tool(server, tool, args)
        if payload is not None:
            trace.append({"step": step_name, "server": server, "tool": tool,
                          "status": "mcp", "ms": int((time.time() - t0) * 1000), "retries": retries})
            return payload
        trace.append({"step": step_name, "server": server, "tool": tool,
                      "status": "local-fallback", "ms": int((time.time() - t0) * 1000), "retries": retries,
                      "error": err or ""})
        return local_fn()

    def _reflect(self, checks, trace, step_name):
        failed = [c for c in checks if not c["passed"]]
        if failed:
            trace.append({"step": step_name, "server": "-", "tool": "validator",
                          "status": "reflection-failed", "ms": 0, "retries": 0,
                          "error": "; ".join(c["detail"] for c in failed)})
        return not failed

    async def analyze(self, request):
        society_id = request["society_id"]
        content = request["content"]
        allow_inference = bool(request.get("allow_inference"))
        data_source = request.get("data_source", "") or ""
        src_label = data_source or "系统内置模拟参数"
        goal = request.get("goal", "提高满意度")
        scope = request.get("scope", "部分群体")
        strength = request.get("strength", "中等")
        trace = []

        ident = await self._call("identify", {"society_id": society_id, "content": content},
                                 lambda: engine.detect(society_id, content), trace)
        if ident.get("status") == "error":
            return {"status": "error", "message": ident.get("message", "识别失败")}
        if ident.get("status") == "mismatch":
            trace.append({"step": "gate", "server": "-", "tool": "mismatch-gate",
                          "status": "blocked", "ms": 0, "retries": 0,
                          "error": "发布内容与当前社会类型不匹配，已拦截并提示用户重新确认"})
            if allow_inference:
                ident = engine.detect(society_id, content, force=True)
                ident["status"] = "ok"
                ident["inferred"] = True
                ident["matched_kw"] = None
                ident["forced_inference"] = True
            else:
                return {
                    "status": "mismatch",
                    "current_society": ident.get("current_society"),
                    "suggested": ident.get("suggested"),
                    "message": ident.get("message"),
                    "trace": trace,
                }

        mismatch_handled = bool(ident.get("forced_inference"))
        if not self._reflect(self.validator.check_identification(ident), trace, "identify"):
            return {"status": "error", "message": "识别结果未通过校验器（约束 1/2）", "trace": trace}

        category_name = ident["category"]["name"]
        inferred = bool(ident.get("inferred"))
        if inferred:
            ident["note"] = "以下为基于当前社会类型的推断：输入未命中「%s」任何规则类别的关键词，系统已按最典型的「%s」进行推断式分析。" % (
                ident["society"]["name"], category_name)

        questionnaire = await self._call(
            "questionnaire", {"society_id": society_id, "category_name": category_name, "content": content},
            lambda: {"sections": engine.build_questionnaire(society_id, category_name, content)}, trace)

        # 公开数据实时拉取：用户选定来源 URL 时尝试获取代表性比例；失败回退预设校准基线
        data_source_url = request.get("data_source_url", "") or ""
        live = await public_fetch.try_live_fetch(data_source_url) if data_source_url \
            else {"ok": False, "reason": "no_url", "ms": 0}

        metrics = await self._call(
            "metrics", {"goal": goal, "scope": scope, "strength": strength,
                        "data_source": data_source, "live": live},
            lambda: engine.simulate_metrics(goal, scope, strength, data_source, live), trace)

        groups = await self._call(
            "groups", {"society_id": society_id, "category_name": category_name,
                       "goal": goal, "scope": scope, "strength": strength},
            lambda: {"groups": engine.deduce_groups(society_id, category_name, goal, scope, strength)}, trace)

        chains = await self._call(
            "chains", {"society_id": society_id, "category_name": category_name,
                       "goal": goal, "scope": scope, "strength": strength},
            lambda: engine.deduce_chains(society_id, category_name, goal, scope, strength), trace)
        if not self._reflect(self.validator.check_chains(chains), trace, "chains"):
            return {"status": "error", "message": "风险链生成未通过校验器（约束 4）", "trace": trace}

        warned = await self._call(
            "vulns", {"society_id": society_id, "category_name": category_name, "content": content,
                      "strength": strength},
            lambda: engine.warn_vulnerabilities(society_id, category_name, content, strength), trace)
        if not self._reflect(self.validator.check_vulns(warned.get("vulns", []), warned.get("audit", {}), content),
                             trace, "vulns"):
            return {"status": "error", "message": "漏洞预警未通过校验器（约束 3）", "trace": trace}

        planned = await self._call(
            "plans", {"society_id": society_id, "category_name": category_name,
                      "risk": metrics.get("risk", 0), "hole": metrics.get("hole", ""),
                      "rec_plan": metrics.get("recPlan", ""),
                      "goal": goal, "scope": scope, "strength": strength},
            lambda: engine.generate_plans(society_id, category_name, metrics), trace)
        plans = planned.get("plans", [])
        rec = planned.get("rec") or {"name": metrics.get("recPlan", ""), "desc": "", "why": ""}
        if not self._reflect(self.validator.check_plans(plans), trace, "plans"):
            return {"status": "error", "message": "方案生成未通过校验器（约束 5）", "trace": trace}

        s, c = engine.category_full(society_id, category_name)
        if plans and rec.get("name"):
            metrics["recPlan"] = rec["name"]
        metrics["recDesc"] = engine.rec_desc(s, c, metrics.get("recPlan", "试点方案"))
        base_conclusion = engine.conclusion(society_id, category_name, content, ident, metrics)
        llm_text = self.gateway.complete(LLM_SYSTEM, _llm_prompt(ident, metrics, warned, rec, chains, content))
        conclusion_html = llm_text if llm_text else base_conclusion
        llm_mode = self.gateway.mode() if llm_text else (self.gateway.mode() + "(fallback:模板)" if self.gateway.enabled else "rule_engine")

        analysis = {
            "society": ident["society"],
            "category": ident["category"],
            "subjects": ident.get("subjects", {}),
            "identification": {
                "society": ident["society"], "category": ident["category"],
                "inferred": inferred, "matched_kw": ident.get("matched_kw"),
                "note": ident.get("note", ""), "direction": ident.get("direction", "调整"),
                "other_society": ident.get("other_society"), "status": "ok",
                "benefits": ident.get("benefits", []),
                "costs": ident.get("costs", []),
                "risks": ident.get("risks", []),
                "data_source": src_label,
            },
            "content": content,
            "goal": goal,
            "scope": scope,
            "strength": strength,
            "attribute_basis": metrics.get("attribute_basis", {}),
            "composite": metrics.get("composite", {}),
            "affected_people": metrics.get("composite", {}).get("affected", 0),
            "benefits": ident.get("benefits", []),
            "costs": ident.get("costs", []),
            "risks": ident.get("risks", []),
            "data_needs": ident.get("data_needs", ""),
            "questionnaire": {"sections": questionnaire.get("sections", []), "data_source": src_label},
            "metrics": metrics,
            "groups": [dict(g, data_source=src_label) for g in groups.get("groups", [])],
            "chains": dict(chains, data_source=src_label),
            "vulns": [dict(v, data_source=src_label) for v in warned.get("vulns", [])],
            "audit": warned.get("audit", {}),
            "plans": [dict(p, data_source=src_label) for p in plans],
            "rec": dict(rec, data_source=src_label),
            "conclusion": conclusion_html,
            "llm_mode": llm_mode,
        }

        validation = self.validator.validate(analysis, mismatch_handled=mismatch_handled, allow_inference=allow_inference)
        run_index = request.get("run_index", 1)
        analysis["report"] = engine.build_report(
            society_id, category_name, content, analysis["identification"], metrics, chains,
            analysis["vulns"], analysis["audit"], plans, rec,
            request.get("data_source", ""), conclusion_html, run_index,
            validation, trace, llm_mode, goal, scope, strength)
        analysis["validation"] = validation
        analysis["trace"] = trace
        return {"status": "ok", "analysis": analysis, "trace": trace}


def _llm_prompt(ident, metrics, warned, rec, chains, content):
    return (
        "发布内容：%s\n场景：%s · %s\n总体赞成度：%d%%，反对度：%d%%，风险指数：%d/100，公平性：%d/100，"
        "漏洞风险：%s，执行难度：%s\n主要漏洞：%s\n推荐方案：%s（%s）\n主风险链：%s"
        % (content, ident["society"]["name"], ident["category"]["name"],
           metrics["approve"], metrics["oppose"], metrics["risk"], metrics["fairness"],
           metrics["hole"], metrics["diff"],
           "、".join(v["name"] for v in warned.get("vulns", [])[:3]),
           rec.get("name", ""), rec.get("desc", ""), " → ".join(chains.get("main", []))))
