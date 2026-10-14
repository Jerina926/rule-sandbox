from knowledge import engine

PLAN_NAMES = {"原方案", "温和方案", "限制方案", "试点方案"}


class Validator:
    def _check(self, cid, name, passed, detail):
        return {"id": cid, "name": name, "passed": bool(passed), "detail": detail}

    def check_identification(self, ident):
        checks = []
        if not isinstance(ident, dict) or not ident.get("society") or not ident.get("category"):
            return [self._check(1, "先识别社会类型与规则类别", False, "识别结果缺失")]
        checks.append(self._check(
            1, "先识别社会类型与规则类别", True,
            "已识别：%s · %s" % (ident["society"].get("name"), ident["category"].get("name"))))
        ok = all(len(ident.get(k, [])) >= 5 for k in ("benefits", "costs", "risks"))
        checks.append(self._check(
            2, "收益/成本/风险各至少 5 条", ok,
            "收益 %d / 成本 %d / 风险 %d" % (len(ident.get("benefits", [])),
                                             len(ident.get("costs", [])), len(ident.get("risks", [])))))
        return checks

    def check_vulns(self, vulns, audit, content):
        ok = len(vulns) >= 3 and not audit.get("violations")
        detail = "漏洞 %d 条，跨场景串词扫描 %d 个外来词，命中 %d 个" % (
            len(vulns), audit.get("scanned", 0), len(audit.get("violations", [])))
        return [self._check(3, "漏洞预警至少 3 条且不跨场景串词", ok, detail)]

    def check_chains(self, chains):
        ok = isinstance(chains, dict) and len(chains.get("main", [])) >= 3 and len(chains.get("alt", [])) >= 3
        return [self._check(4, "风险链 1 条主链 + 1 条备选链", ok,
                            "主链 %d 节点，备选链 %d 节点" % (len(chains.get("main", [])) if isinstance(chains, dict) else 0,
                                                              len(chains.get("alt", [])) if isinstance(chains, dict) else 0))]

    def check_plans(self, plans):
        names = {p.get("name") for p in plans}
        ok = len(plans) >= 4 and PLAN_NAMES.issubset(names)
        return [self._check(5, "替代方案至少 4 个且含原/温和/限制/试点", ok,
                            "已生成 %d 个方案：%s" % (len(plans), "、".join(sorted(names & PLAN_NAMES))))]

    def check_inference(self, ident, mismatch_handled, allow_inference):
        inferred = bool(ident.get("inferred"))
        marked = (not inferred) or ("推断" in (ident.get("note") or "")) or allow_inference
        detail = "推断模式" if inferred else "高置信关键词匹配"
        if inferred and allow_inference:
            detail += "（用户确认后按推断继续，已标注）"
        return [self._check(6, "输入超限时按社会类型推断并标注", marked, detail)]

    def check_mismatch_gate(self, ident, mismatch_handled):
        ok = not mismatch_handled or bool(ident.get("status") == "ok")
        detail = "未触发不匹配拦截" if not mismatch_handled else "触发拦截并经用户确认后重新识别"
        return [self._check(7, "类型不匹配时提示确认而非强行生成", ok, detail)]

    def validate(self, analysis, mismatch_handled=False, allow_inference=False):
        ident = analysis.get("identification", {})
        checks = []
        checks += self.check_identification(ident)
        checks += self.check_vulns(analysis.get("vulns", []), analysis.get("audit", {}), analysis.get("content", ""))
        checks += self.check_chains(analysis.get("chains", {}))
        checks += self.check_plans(analysis.get("plans", []))
        checks += self.check_inference(ident, mismatch_handled, allow_inference)
        checks += self.check_mismatch_gate(ident, mismatch_handled)
        return {"passed": all(c["passed"] for c in checks), "checks": checks}

    def cross_terms(self, society_id):
        return engine.cross_terms(society_id)
