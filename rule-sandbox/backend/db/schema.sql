-- 规则沙盒 SQLite schema（5 张表）
-- 用法：sqlite3 rule_sandbox.db < schema.sql
-- 或由 backend/db/store.py 在启动时执行

-- ============================================================
-- 1) cases：每次 analyze 调用的主案例表
--    业务主键 case_id = session_id + run_index（保证一次会话内唯一）
-- ============================================================
CREATE TABLE IF NOT EXISTS cases (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  case_id         TEXT UNIQUE NOT NULL,
  session_id      TEXT NOT NULL,
  run_index       INTEGER NOT NULL,
  society_id      TEXT NOT NULL,
  category_name   TEXT,
  content         TEXT NOT NULL,
  goal            TEXT DEFAULT '',
  scope           TEXT DEFAULT '',
  strength        TEXT DEFAULT '',
  inferred        INTEGER DEFAULT 0,
  allow_inference INTEGER DEFAULT 0,
  status          TEXT NOT NULL,
  error_message   TEXT,
  approve         INTEGER,
  oppose          INTEGER,
  risk            INTEGER,
  fairness        INTEGER,
  rec_plan        TEXT,
  created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_cases_session ON cases(session_id, run_index);
CREATE INDEX IF NOT EXISTS idx_cases_society ON cases(society_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cases_created ON cases(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cases_status  ON cases(status, created_at DESC);

-- ============================================================
-- 2) questionnaires：每 case 1:1 关联问卷题目
--    sections 字段是 JSON 字符串存储 7 个分区的所有题 + 选项
-- ============================================================
CREATE TABLE IF NOT EXISTS questionnaires (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  case_id       TEXT UNIQUE NOT NULL,
  sections      TEXT NOT NULL,
  section_count INTEGER NOT NULL,
  item_count    INTEGER NOT NULL,
  created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_q_case ON questionnaires(case_id);

-- ============================================================
-- 3) answers：每条题目作答一行（支持用户作答 / 自动模拟作答）
--    selected 为 NULL 时表示"未作答"
--    source 区分来源：'frontend' 用户实际作答；'engine' 规则引擎默认；'simulated' 仿真推演
-- ============================================================
CREATE TABLE IF NOT EXISTS answers (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  case_id       TEXT NOT NULL,
  section       TEXT NOT NULL,
  question      TEXT NOT NULL,
  options_json  TEXT NOT NULL,
  selected      TEXT,
  source        TEXT DEFAULT 'frontend',
  source_ref    TEXT,
  created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_a_case ON answers(case_id, section);
CREATE INDEX IF NOT EXISTS idx_a_section ON answers(section);

-- ============================================================
-- 4) public_sources：公开数据源引用
--    society_id NULL 表示通用数据源（适用于所有社会）
--    UNIQUE(society_id, name) 保证同一社会下同名去重
-- ============================================================
CREATE TABLE IF NOT EXISTS public_sources (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  society_id  TEXT,
  name        TEXT NOT NULL,
  url         TEXT,
  category    TEXT,
  use_field   TEXT,
  source      TEXT DEFAULT 'kb_internal',
  created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(society_id, name)
);
CREATE INDEX IF NOT EXISTS idx_s_society ON public_sources(society_id, category);
CREATE INDEX IF NOT EXISTS idx_s_category ON public_sources(category);

-- ============================================================
-- 5) simulation_reports：仿真报告主表
--    case_id 1:1 关联 cases；report_md 是 build_report() 输出的完整 Markdown
-- ============================================================
CREATE TABLE IF NOT EXISTS simulation_reports (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
  case_id             TEXT UNIQUE NOT NULL,
  conclusion          TEXT NOT NULL,
  llm_mode            TEXT,
  validation_passed   INTEGER DEFAULT 0,
  validation_summary  TEXT,
  trace_json          TEXT,
  report_md           TEXT,
  explanation_json    TEXT,
  created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (case_id) REFERENCES cases(case_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_r_case ON simulation_reports(case_id);
CREATE INDEX IF NOT EXISTS idx_r_created ON simulation_reports(created_at DESC);
