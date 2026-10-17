"""5 张表的仓储：保存 / 查询 / 对比 / 统计。

关键设计：
- persist() 在分析完成时被调用；任何步骤失败都只记录错误，不抛出，避免破坏主流程。
- 所有 JSON 列在写入时序列化，读出时反序列化。
- list_cases 支持按 society_id / 状态 / 时间窗筛选 + 分页。
- compare_cases 输出多 case 的并列摘要（用于挑战杯现场「同社会不同规则对比」「跨社会同规则对比」）。
"""
import json
import os
import sys
import time

from . import get_conn, row_to_dict, rows_to_list, tx, resolve_db_path


def _now_ts():
    return int(time.time())


def _safe_json_dumps(obj, default="{}"):
    try:
        if obj is None:
            return default
        return json.dumps(obj, ensure_ascii=False)
    except (TypeError, ValueError):
        return default


def _safe_json_loads(s, default=None):
    if default is None:
        default = {}
    if not s:
        return default
    try:
        return json.loads(s)
    except (TypeError, ValueError):
        return default


# ============================================================
# CasesRepo
# ============================================================

class CasesRepo:

    @staticmethod
    def persist(analysis, request=None, error_message=""):
        """主入口：把一次成功的 analyze 结果写进 5 张表。

        analysis 字段要求（与现有 planner.analyze 输出一致）：
          society / category / identification / content / goal / scope / strength
          benefits / costs / risks
          questionnaire.sections
          metrics {approve, oppose, risk, fairness, recPlan}
          plans / rec / conclusion / llm_mode / report / validation / trace / explanation
        """
        try:
            return CasesRepo._persist_inner(analysis, request, error_message)
        except Exception as e:
            sys.stderr.write("[CasesRepo.persist] error: %s\n" % e)
            return {"ok": False, "error": str(e)}

    @staticmethod
    def _persist_inner(analysis, request, error_message):
        ident = analysis.get("identification", {}) or {}
        society = analysis.get("society", {}) or {}
        cat = analysis.get("category", {}) or {}
        content = analysis.get("content") or (request or {}).get("content", "")
        session_id = analysis.get("session_id") or (request or {}).get("session_id") or "anon"
        run_index = int(analysis.get("run_index") or 1)
        case_id = "%s#%d" % (session_id, run_index)

        # 1) cases 主表
        status = analysis.get("status", "ok") if "status" in analysis else "ok"
        metrics = analysis.get("metrics", {}) or {}
        params = [
            case_id, session_id, run_index,
            society.get("id") or (request or {}).get("society_id", ""),
            cat.get("name") or "",
            content,
            analysis.get("goal") or (request or {}).get("goal", ""),
            analysis.get("scope") or (request or {}).get("scope", ""),
            analysis.get("strength") or (request or {}).get("strength", ""),
            1 if ident.get("inferred") else 0,
            1 if (request or {}).get("allow_inference") else 0,
            status, error_message,
            metrics.get("approve"), metrics.get("oppose"),
            metrics.get("risk"), metrics.get("fairness"),
            metrics.get("recPlan"),
        ]
        with tx() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cases "
                "(case_id, session_id, run_index, society_id, category_name, content, "
                " goal, scope, strength, inferred, allow_inference, status, error_message, "
                " approve, oppose, risk, fairness, rec_plan) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                params)

            # 2) questionnaires
            q = analysis.get("questionnaire", {}) or {}
            sections = q.get("sections", []) or []
            item_count = sum(len(s.get("qs", [])) for s in sections)
            conn.execute(
                "INSERT OR REPLACE INTO questionnaires "
                "(case_id, sections, section_count, item_count) VALUES (?, ?, ?, ?)",
                [case_id, _safe_json_dumps(sections, "[]"),
                 len(sections), item_count])

            # 3) answers：先写空行（占位），让每个题目可独立查询
            for sec in sections:
                sec_name = sec.get("name", "")
                for qa in (sec.get("qs") or []):
                    if isinstance(qa, list) and qa:
                        question = qa[0]
                        options = qa[1] if len(qa) > 1 else []
                        conn.execute(
                            "INSERT INTO answers "
                            "(case_id, section, question, options_json, selected, source, source_ref) "
                            "VALUES (?, ?, ?, ?, NULL, 'engine', ?)",
                            [case_id, sec_name, question,
                             _safe_json_dumps(options, "[]"),
                             sec.get("desc", sec_name)])

            # 4) public_sources：从 5 个可解释模型的 evidence_refs 写入
            explanation = analysis.get("explanation") or {}
            for model_key, model_data in explanation.items():
                if model_key.startswith("_"):
                    continue
                refs = (model_data or {}).get("evidence_refs", []) if isinstance(model_data, dict) else []
                for ref in refs:
                    if not isinstance(ref, dict):
                        continue
                    name = ref.get("name", "")
                    if not name:
                        continue
                    try:
                        conn.execute(
                            "INSERT OR IGNORE INTO public_sources "
                            "(society_id, name, url, category, use_field, source) "
                            "VALUES (?, ?, ?, ?, ?, ?)",
                            [society.get("id") or "", name, ref.get("url") or "",
                             (request or {}).get("category", "") or "general",
                             ref.get("use", "")[:200] if ref.get("use") else "",
                             "explainable_model"])
                    except Exception:
                        pass  # 重复插入自然 IGNORE，不抛错
            # 知识库自带的 data 字符串也作为去重的 source
            soc_data = society.get("data") if isinstance(society.get("data"), str) else ""
            if soc_data:
                try:
                    conn.execute(
                        "INSERT OR IGNORE INTO public_sources "
                        "(society_id, name, url, category, use_field, source) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        [society.get("id") or "", soc_data, "",
                         "general", "知识库内置数据来源", "kb_internal"])
                except Exception:
                    pass

            # 5) simulation_reports
            validation = analysis.get("validation", {}) or {}
            v_checks = validation.get("checks", []) if isinstance(validation, dict) else []
            v_summary = {
                "passed": validation.get("passed", 0),
                "total": len(v_checks),
                "failures": [{"name": c.get("name"), "detail": c.get("detail")}
                              for c in v_checks if not c.get("passed")]
            }
            conn.execute(
                "INSERT OR REPLACE INTO simulation_reports "
                "(case_id, conclusion, llm_mode, validation_passed, validation_summary, "
                " trace_json, report_md, explanation_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [case_id,
                 analysis.get("conclusion", ""),
                 analysis.get("llm_mode", ""),
                 1 if validation.get("passed") else 0,
                 _safe_json_dumps(v_summary),
                 _safe_json_dumps(analysis.get("trace", [])),
                 analysis.get("report", "") or "",
                 _safe_json_dumps(explanation)])

        return {"ok": True, "case_id": case_id,
                "sections": len(sections), "items": item_count,
                "db_path": resolve_db_path()}

    @staticmethod
    def upsert_answers(case_id, user_answers):
        """用户在答完问卷后调用：把 selected 写入对应行。
        user_answers 形如 [{section, question, selected}, ...]"""
        try:
            n = 0
            with tx() as conn:
                for ans in user_answers or []:
                    cur = conn.execute(
                        "SELECT id FROM answers WHERE case_id=? AND section=? AND question=?",
                        [case_id, ans.get("section", ""), ans.get("question", "")])
                    row = cur.fetchone()
                    if row:
                        conn.execute(
                            "UPDATE answers SET selected=?, source='frontend' WHERE id=?",
                            [ans.get("selected", ""), row["id"]])
                        n += 1
            return {"ok": True, "updated": n}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @staticmethod
    def list_cases(society_id="", limit=50, offset=0, days=None, status=""):
        sql = ("SELECT case_id, session_id, run_index, society_id, category_name, "
               "content, goal, scope, strength, status, approve, oppose, risk, fairness, "
               "rec_plan, created_at FROM cases WHERE 1=1")
        params = []
        if society_id:
            sql += " AND society_id=?"; params.append(society_id)
        if status:
            sql += " AND status=?"; params.append(status)
        if days is not None and days > 0:
            sql += " AND created_at >= datetime('now', ?)"; params.append("-%d days" % days)
        sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, max(0, offset)])
        with tx() as conn:
            cur = conn.execute(sql, params)
            return rows_to_list(cur.fetchall())

    @staticmethod
    def get_case(case_id):
        """单 case 完整详情（含问卷/答案/报告/解释）"""
        conn = get_conn()
        c = conn.execute("SELECT * FROM cases WHERE case_id=?", [case_id]).fetchone()
        if not c:
            return None
        out = row_to_dict(c)
        q = conn.execute("SELECT * FROM questionnaires WHERE case_id=?", [case_id]).fetchone()
        if q:
            qd = row_to_dict(q)
            qd["sections"] = _safe_json_loads(qd["sections"], [])
            out["questionnaire"] = qd
        a = conn.execute("SELECT section, question, selected, source, source_ref, created_at "
                         "FROM answers WHERE case_id=? ORDER BY id", [case_id]).fetchall()
        out["answers"] = rows_to_list(a)
        r = conn.execute("SELECT * FROM simulation_reports WHERE case_id=?", [case_id]).fetchone()
        if r:
            rd = row_to_dict(r)
            rd["validation_summary"] = _safe_json_loads(rd["validation_summary"], {})
            rd["trace_json"] = _safe_json_loads(rd["trace_json"], [])
            rd["explanation_json"] = _safe_json_loads(rd["explanation_json"], {})
            out["simulation_report"] = rd
        return out

    @staticmethod
    def compare_cases(case_ids):
        """多 case 并列对比：返回每个 case 的关键指标 + 结论节选"""
        if not case_ids:
            return []
        with tx() as conn:
            placeholders = ",".join(["?"] * len(case_ids))
            cur = conn.execute(
                "SELECT c.case_id, c.society_id, c.category_name, c.content, c.scope, c.strength, "
                " c.approve, c.oppose, c.risk, c.fairness, c.rec_plan, c.created_at, "
                " r.conclusion, r.rec_plan as r_rec, r.llm_mode, r.validation_passed "
                "FROM cases c LEFT JOIN simulation_reports r ON c.case_id=r.case_id "
                "WHERE c.case_id IN (%s) ORDER BY c.created_at" % placeholders,
                case_ids)
            return rows_to_list(cur.fetchall())

    @staticmethod
    def stats(days=30):
        """统计：案例总数 / 状态分布 / 风险均值 / 按社会分布"""
        with tx() as conn:
            total = conn.execute(
                "SELECT COUNT(*) c FROM cases WHERE created_at >= datetime('now', ?) ",
                ["-%d days" % days]).fetchone()["c"]
            by_status = rows_to_list(conn.execute(
                "SELECT status, COUNT(*) c FROM cases WHERE created_at >= datetime('now', ?) "
                "GROUP BY status", ["-%d days" % days]).fetchall())
            by_society = rows_to_list(conn.execute(
                "SELECT society_id, COUNT(*) c, ROUND(AVG(risk), 1) avg_risk, "
                " ROUND(AVG(approve), 1) avg_approve "
                "FROM cases WHERE status='ok' AND created_at >= datetime('now', ?) "
                "GROUP BY society_id ORDER BY c DESC", ["-%d days" % days]).fetchall())
            by_plan = rows_to_list(conn.execute(
                "SELECT rec_plan, COUNT(*) c FROM cases WHERE status='ok' "
                "AND created_at >= datetime('now', ?) GROUP BY rec_plan ORDER BY c DESC",
                ["-%d days" % days]).fetchall())
            conn.execute("SELECT 1").fetchall()  # touch
        return {"window_days": days, "total_cases": total,
                "by_status": by_status, "by_society": by_society, "by_plan": by_plan,
                "db_path": resolve_db_path()}

    @staticmethod
    def delete_case(case_id):
        with tx() as conn:
            conn.execute("DELETE FROM cases WHERE case_id=?", [case_id])
        return {"ok": True, "case_id": case_id}


# ============================================================
# SourcesRepo
# ============================================================

class SourcesRepo:

    @staticmethod
    def list_sources(society_id="", category=""):
        sql = "SELECT society_id, name, url, category, use_field, source FROM public_sources WHERE 1=1"
        params = []
        if society_id:
            sql += " AND society_id=?"; params.append(society_id)
        if category:
            sql += " AND category=?"; params.append(category)
        sql += " ORDER BY society_id, category, id"
        with tx() as conn:
            return rows_to_list(conn.execute(sql, params).fetchall())

    @staticmethod
    def add_source(society_id, name, url="", category="general", use_field="", source="manual"):
        with tx() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO public_sources "
                "(society_id, name, url, category, use_field, source) VALUES (?, ?, ?, ?, ?, ?)",
                [society_id, name, url, category, use_field, source])
        return {"ok": True}
