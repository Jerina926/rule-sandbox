"""SQLite 的 GitHub 免费持久化备份。

原理：
- 备份：WAL checkpoint 后读取 db 文件，base64 提交到仓库 db-snapshot 分支
- 恢复：启动时若本地 db 不存在（Render 重新部署后磁盘被清空），从该分支下载恢复
- 通过环境变量启用：RSB_GH_TOKEN（fine-grained PAT，仅需该仓库 Contents 读写）+ RSB_GH_REPO（如 Jerina926/rule-sandbox）
- 未配置时全部静默跳过，不影响本地/原有运行
"""
import base64
import io
import json
import os
import sqlite3
import urllib.request
import zipfile

_API = "https://api.github.com"
_BRANCH = "db-snapshot"
_FILE = "rule_sandbox.db"
_SESSIONS_FILE = "sessions.zip"


def _conf():
    return os.environ.get("RSB_GH_TOKEN", "").strip(), os.environ.get("RSB_GH_REPO", "").strip()


def enabled():
    t, r = _conf()
    return bool(t and r)


def _req(method, url, token, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", "Bearer " + token)
    req.add_header("Accept", "application/vnd.github+json")
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def _branch_sha(token, repo):
    ref = _req("GET", f"{_API}/repos/{repo}/git/ref/heads/{_BRANCH}", token)
    return ref["object"]["sha"]


def _ensure_branch(token, repo):
    try:
        return _branch_sha(token, repo)
    except Exception:
        default = _req("GET", f"{_API}/repos/{repo}", token)["default_branch"]
        base = _req("GET", f"{_API}/repos/{repo}/git/ref/heads/{default}", token)["object"]["sha"]
        _req("POST", f"{_API}/repos/{repo}/git/refs", token,
             {"ref": f"refs/heads/{_BRANCH}", "sha": base})
        return base


def restore(db_path):
    """启动时调用：本地无 db 文件时从 GitHub 恢复。返回是否执行了恢复。"""
    token, repo = _conf()
    if not enabled():
        return False
    if os.path.exists(db_path) and os.path.getsize(db_path) > 0:
        return False
    try:
        content = _req("GET", f"{_API}/repos/{repo}/contents/{_FILE}?ref={_BRANCH}", token)
        data = base64.b64decode(content["content"])
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        with open(db_path, "wb") as f:
            f.write(data)
        print(f"DB restored from GitHub backup: {len(data)} bytes -> {db_path}", flush=True)
        return True
    except Exception as e:
        print("DB restore skipped:", e, flush=True)
        return False


def backup(db_path):
    """备份当前 db 文件到 db-snapshot 分支。返回是否成功。"""
    token, repo = _conf()
    if not enabled() or not os.path.exists(db_path):
        return False
    try:
        # 先截断 WAL，保证备份文件包含全部已提交数据
        with sqlite3.connect(db_path) as conn:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        with open(db_path, "rb") as f:
            blob = base64.b64encode(f.read()).decode()
        sha = _ensure_branch(token, repo)
        try:
            old = _req("GET", f"{_API}/repos/{repo}/contents/{_FILE}?ref={_BRANCH}", token)
            payload = {"message": "chore: db snapshot", "branch": _BRANCH,
                       "content": blob, "sha": old["sha"]}
        except Exception:
            payload = {"message": "chore: db snapshot", "branch": _BRANCH, "content": blob}
        _req("PUT", f"{_API}/repos/{repo}/contents/{_FILE}", token, payload)
        print("DB backed up to GitHub", flush=True)
        return True
    except Exception as e:
        print("DB backup failed:", e, flush=True)
        return False


def restore_sessions(sessions_dir):
    """启动时调用：本地 sessions 目录无任何会话 JSON 时从 GitHub 恢复。返回是否执行了恢复。"""
    token, repo = _conf()
    if not enabled():
        return False
    try:
        os.makedirs(sessions_dir, exist_ok=True)
        if any(f.endswith(".json") for f in os.listdir(sessions_dir)):
            return False
        content = _req("GET", f"{_API}/repos/{repo}/contents/{_SESSIONS_FILE}?ref={_BRANCH}", token)
        data = base64.b64decode(content["content"])
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = [n for n in zf.namelist() if n.endswith(".json")]
            zf.extractall(sessions_dir)
        print(f"Sessions restored from GitHub backup: {len(names)} files -> {sessions_dir}", flush=True)
        return True
    except Exception as e:
        print("Sessions restore skipped:", e, flush=True)
        return False


def backup_sessions(sessions_dir):
    """把 sessions 目录下的会话 JSON 打包成 sessions.zip 上传到 db-snapshot 分支。返回是否成功。"""
    token, repo = _conf()
    if not enabled() or not os.path.isdir(sessions_dir):
        return False
    files = sorted(f for f in os.listdir(sessions_dir) if f.endswith(".json"))
    if not files:
        return False
    try:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in files:
                zf.write(os.path.join(sessions_dir, f), f)
        blob = base64.b64encode(buf.getvalue()).decode()
        sha = _ensure_branch(token, repo)
        try:
            old = _req("GET", f"{_API}/repos/{repo}/contents/{_SESSIONS_FILE}?ref={_BRANCH}", token)
            payload = {"message": "chore: sessions snapshot", "branch": _BRANCH,
                       "content": blob, "sha": old["sha"]}
        except Exception:
            payload = {"message": "chore: sessions snapshot", "branch": _BRANCH, "content": blob}
        _req("PUT", f"{_API}/repos/{repo}/contents/{_SESSIONS_FILE}", token, payload)
        print(f"Sessions backed up to GitHub: {len(files)} files", flush=True)
        return True
    except Exception as e:
        print("Sessions backup failed:", e, flush=True)
        return False
