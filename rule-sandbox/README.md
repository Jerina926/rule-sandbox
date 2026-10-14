# 规则沙盒：虚拟社会反应预演系统（生产级）

前端网页 + FastAPI 智能体编排层 + 4 个独立标准 MCP-Server 工具 + LLM-API 网关。
严格基于 MCP 协议（stdio 传输），分层解耦，支持插件热插拔、多步规划反思、会话持久记忆、请求重试。

## 一、项目目录结构

```
rule-sandbox/
├── config.yaml                     # 全局配置（服务端口 / MCP Server 注册表 / LLM 网关 / 会话存储）
├── requirements.txt                # Python 依赖
├── README.md                       # 本文档
├── knowledge/                      # 场景知识库与共享分析引擎
│   ├── __init__.py
│   ├── kb.py                       # 8 类虚拟社会 × 44 个规则类别专属知识库
│   └── engine.py                   # 识别 / 问卷 / 指标 / 主体 / 风险链 / 漏洞 / 方案 / 报告引擎
├── mcp_servers/                    # 4 个独立标准 MCP-Server（stdio 传输，可单独运行调试）
│   ├── society_identification_server.py   # 社会识别：list_societies / identify / build_questionnaire
│   ├── risk_chain_server.py               # 风险链推演：simulate_metrics / deduce_groups / deduce_chains
│   ├── vulnerability_warning_server.py    # 漏洞预警：warn_vulnerabilities（含跨场景串词审计）
│   └── plan_generation_server.py          # 方案生成：generate_plans
├── backend/
│   ├── main.py                     # FastAPI 入口（含静态托管 frontend/）
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py               # 顶层 HTTP 接口
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── planner.py              # Planner 任务规划器：多步规划 → MCP 调用 → 反思校验 → 重试/降级
│   │   └── session_store.py        # 会话持久存储（JSON 文件落盘，跨重启保留）
│   ├── core/
│   │   ├── __init__.py
│   │   ├── mcp_manager.py          # 全局 MCP 客户端管理器（连接池 / 重试 / 热插拔）
│   │   ├── llm_gateway.py          # LLM-API 网关（未配置 key 时自动降级规则引擎）
│   │   └── validator.py            # 规则校验器（7 条约束全部内置）
│   └── data/
│       └── sessions/               # 会话持久化数据目录
└── frontend/
    └── index.html                  # 12 步交互式前端（在线走后端 / 离线自动回退本地引擎）
```

## 二、分步启动文档

### 第 1 步：安装依赖

```bash
cd rule-sandbox
pip install -r requirements.txt
```

依赖清单：`fastapi`、`uvicorn[standard]`、`mcp>=1.2,<2`（MCP SDK 1.x，FastMCP 位于 `mcp.server.fastmcp`）、`pyyaml`、`httpx`。

### 第 2 步：检查配置

`config.yaml` 关键项：

```yaml
server: {host: 127.0.0.1, port: 8017}
mcp:
  servers:                       # 4 个 MCP Server 注册表（stdio 子进程，支持热插拔增删）
    society-identification: {command: python, args: [mcp_servers/society_identification_server.py]}
    risk-chain:                {command: python, args: [mcp_servers/risk_chain_server.py]}
    vulnerability-warning:     {command: python, args: [mcp_servers/vulnerability_warning_server.py]}
    plan-generation:           {command: python, args: [mcp_servers/plan_generation_server.py]}
llm:
  enabled: false                # 置 true 并填 api_key / base_url / model 后启用 LLM 增强结论
  api_key: ""
  base_url: "https://api.example.com/v1"
  model: "gpt-4o-mini"
session: {dir: backend/data/sessions}
```

### 第 3 步：单独调试 MCP Server（可选）

任一 MCP Server 均可独立运行（stdio JSON-RPC）：

```bash
python mcp_servers/society_identification_server.py
```

### 第 4 步：启动后端（自动拉起 4 个 MCP 子进程）

```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8017
```

### 第 5 步：访问前端

浏览器打开 `http://127.0.0.1:8017/`（后端直接托管 `frontend/index.html`）。
顶栏显示「后端已连接 · MCP」徽标表示在线模式；后端不可用时自动回退内置本地引擎，页面仍可完整演示。

### 第 6 步：验证

```bash
curl http://127.0.0.1:8017/api/health     # 4 个 server connected: true 即就绪
```

## 三、HTTP 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | 健康检查：LLM 模式、会话数、各 MCP Server 连接状态与工具清单 |
| GET | `/api/societies` | 8 类虚拟社会元数据（主体 / 适用场景 / 规则类别） |
| POST | `/api/analyze` | 完整分析流水线（见下方请求字段） |
| GET | `/api/sessions` | 会话列表 |
| GET | `/api/sessions/{sid}` | 单会话详情（含历史 runs） |
| POST | `/api/mcp/reload` | MCP Server 热插拔重载 |

`/api/analyze` 请求字段：

- `society_id`：虚拟社会 id（school / country / community / company / ecom / medical / traffic / content）
- `content`：发布内容（自然语言）
- `goal` / `scope` / `strength`：发布目标 / 范围 / 强度（可选）
- `session_id`：会话 id（可选，传入即延续历史记忆，run_index 递增）
- `allow_inference`：不匹配拦截后，用户确认「仍按当前类型推断分析」时传 true

返回 `status`：

- `ok`：`analysis` 内含 identification / questionnaire / metrics / groups / chains(主+备) / vulns / plans(4 个) / rec / report / validation / trace
- `mismatch`：内容与当前社会类型不匹配，返回 `suggested` 建议切换的社会类型，不强行生成
- `error`：校验器拦截，`trace` 内含失败步骤

## 四、校验器内置的 7 条约束

1. 每次先识别社会类型与规则类别；
2. 收益 / 成本 / 风险各至少 5 条（44 个类别全量校验通过）；
3. 漏洞预警至少 3 条，且跨场景串词扫描命中 0（全库唯一签名词 + 本社会全量词表白名单）；
4. 风险链 1 条主链 + 1 条备选链；
5. 替代方案至少 4 个：原方案 / 温和方案 / 限制方案 / 试点方案；
6. 输入未命中关键词时按社会类型推断，并在结果中标注「以下为基于当前社会类型的推断」；
7. 内容与社会类型明显不匹配时返回 mismatch 拦截，经用户确认（切换或 allow_inference）后才继续。

## 五、架构说明

- **Planner**：按固定 DAG 规划 7 步任务（identify → questionnaire → metrics → groups → chains → vulns → plans），每步优先调 MCP Server，失败自动重试后降级本地引擎；每步结果经反思校验器（Validator）检查，不通过则中止并返回失败轨迹。
- **MCP 管理器**：按 config.yaml 注册表管理 stdio 子进程连接池，支持运行时 `POST /api/mcp/reload` 热插拔增删 Server。
- **LLM 网关**：配置 key 后用于增强总体结论；未配置或调用失败自动回退知识库模板，流水线不中断。
- **会话存储**：每次分析以 run 记录追加至会话文件，跨服务重启持久保留，`session_id` 传入即可延续。
- **前端**：12 步流程页全部优先消费后端 `/api/analyze` 结果；探测失败自动回退内置引擎，离线可演示。
