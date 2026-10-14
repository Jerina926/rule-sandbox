# 规则沙盒后端 — 云端部署指南（Render / Railway）

目标架构：**前端公网（静态托管）+ 后端公网 API（Render/Railway）**
前端通过 `API_BASE` 跨域调用后端，实现「智能体增强模式」。

---

## 一、部署前须知

- 后端为纯 Python（FastAPI + 4 个 stdio MCP Server 子进程），无需数据库、无需 Node
- 全部路径已做云适配（绝对路径 + `sys.executable`），仓库根目录 = `rule-sandbox/`
- 会话数据写入 `backend/data/sessions/`（JSON 文件，云平台重启会丢失，属预期行为）

## 二、部署到 Render（推荐，免费档够用）

1. **推送代码到 GitHub**
   把 `rule-sandbox/` 目录作为仓库根目录推送到一个新 GitHub 仓库（不要把整个工作目录推上去，只推 `rule-sandbox/` 内的全部内容）。

2. **创建 Web Service**
   - Render 控制台 → New → **Web Service** → 连接该 GitHub 仓库
   - Language / Runtime: **Python 3**
   - Build Command:
     ```
     pip install -r requirements.txt
     ```
   - Start Command:
     ```
     uvicorn backend.main:app --host 0.0.0.0 --port $PORT
     ```
   - Instance Type: Free

3. **环境变量（可选）**
   | 变量 | 值 | 说明 |
   |---|---|---|
   | `RSB_MODE` | `cloud` | health 返回的 mode 字段标识云端部署 |
   | `RSB_MCP_ENABLED` | `1`（默认）| 设为 `0` 可跳过 MCP 子进程，纯本地引擎模式（部署排障时用）|
   | `RSB_CORS_ORIGINS` | 逗号分隔的域名 | 追加允许的前端域名（默认已含 workbuddy 域名）|

4. **验证**
   - 等待构建完成（首次约 3~5 分钟）
   - 访问 `https://你的服务名.onrender.com/api/health`
   - 应返回 `{"status":"ok","mode":"cloud","llm_mode":"rule_engine",...,"servers":{...全部 connected:true}}`
   - ⚠️ 免费档闲置 15 分钟会休眠，首次唤醒约需 30~60 秒，health 探测超时属正常，刷新一次即可

## 三、部署到 Railway

1. Railway 控制台 → New Project → **Deploy from GitHub repo** → 选择仓库
2. Railway 会自动识别 Python；在 **Settings → Deploy** 中把 Start Command 改为：
   ```
   uvicorn backend.main:app --host 0.0.0.0 --port $PORT
   ```
   （或在仓库根目录放 `Procfile`，内容：`web: uvicorn backend.main:app --host 0.0.0.0 --port $PORT`）
3. Settings → Networking → **Generate Domain**，得到公网地址
4. 验证方式同上（Railway 无冷启动休眠问题）

## 四、把后端地址接回前端

1. 打开 `frontend/index.html`，找到：
   ```js
   const API_BASE_CANDIDATES = ["https://your-backend-url.com", "", "http://127.0.0.1:8017"];
   ```
2. 把第一项替换为真实后端地址，例如：
   ```js
   const API_BASE_CANDIDATES = ["https://你的服务名.onrender.com", "", "http://127.0.0.1:8017"];
   ```
3. 重新部署/发布前端静态托管
4. 打开前端页面，顶栏应显示「智能体增强模式 · 已接入 ↗」绿色徽标

## 五、CORS 说明

后端已在 `backend/main.py` 内置 CORS 白名单，默认允许：
- `https://9aa6eec419d14da9a75443262bfbc669.app.workbuddy.host`（你的前端公网域名）
- `http://127.0.0.1:8017` / `http://localhost:8017`（本地调试）
- 追加域名两种方式：改 `config.yaml` 的 `cors.origins`，或设环境变量 `RSB_CORS_ORIGINS`

## 六、常见问题

| 现象 | 原因与处理 |
|---|---|
| health 里 servers 全是 connected:false | MCP 子进程启动失败——先设 `RSB_MCP_ENABLED=0` 排障，系统会自动降级本地引擎，分析功能不受影响 |
| 前端徽标一直是「待接入」 | 后端地址没替换占位符，或后端处于冷启动休眠中（免费档），先手动访问一次 health 唤醒 |
| 浏览器控制台报 CORS 错误 | 前端域名不在白名单——用 `RSB_CORS_ORIGINS` 环境变量追加后重新部署 |
| analyze 很慢 | 免费档冷启动，第二次起恢复正常（正常耗时 <100ms）|
