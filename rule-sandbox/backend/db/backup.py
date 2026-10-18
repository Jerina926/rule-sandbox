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
import urllib.error
import urllib.request
import zipfile

_API = "https://api.github.com"
_BRANCH = "db-snapshot"
_FILE = "rule_sandbox.db"
_SESSIONS_FILE = "sessions.zip"
_MAX_PART = 900 * 1024  # GitHub 单文件约 1MB 上限，留 10% 余量


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


def _safe_name(n):
    """zip 条目名必须与 basename 一致且不含路径穿越，防止恶意快照往会话目录外写文件。"""
    return n == os.path.basename(n) and ".." not in n


def _get_blob(token, repo, path):
    """下载快照文件内容；文件不存在返回 None，其余错误向上抛。"""
    try:
        r = _req("GET", f"{_API}/repos/{repo}/contents/{path}?ref={_BRANCH}", token)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    return base64.b64decode(r["content"])


def _put_file(token, repo, path, data, message):
    """上传（创建或更新）单个快照文件，GitHub API 要求 base64 content。"""
    blob = base64.b64encode(data).decode()
    try:
        old = _req("GET", f"{_API}/repos/{repo}/contents/{path}?ref={_BRANCH}", token)
        payload = {"message": message, "branch": _BRANCH, "content": blob, "sha": old["sha"]}
    except Exception:
        payload = {"message": message, "branch": _BRANCH, "content": blob}
    _req("PUT", f"{_API}/repos/{repo}/contents/{path}", token, payload)


def _delete_if_exists(token, repo, path):
    """删除快照文件（GitHub 删除需先取 sha）；文件不存在或失败返回 False。"""
    try:
        old = _req("GET", f"{_API}/repos/{repo}/contents/{path}?ref={_BRANCH}", token)
        _req("DELETE", f"{_API}/repos/{repo}/contents/{path}", token,
             {"message": "chore: remove stale snapshot", "branch": _BRANCH, "sha": old["sha"]})
        return True
    except Exception:
        return False


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
    """启动时调用：从 GitHub 快照补齐本地缺失的会话文件。

    只补缺、不覆盖：已有文件说明是本地更新数据，保留；GitHub 快照有而本地缺的
    文件（重部署磁盘清空或残留不完整时）补进来。快照优先读单文件 sessions.zip，
    不存在时按序合并分卷 sessions.zip.001/002…。返回是否补入了文件。
    """
    token, repo = _conf()
    if not enabled():
        return False
    try:
        os.makedirs(sessions_dir, exist_ok=True)
        data = _get_blob(token, repo, _SESSIONS_FILE)
        if data is None:
            chunks, i = [], 1
            while True:
                part = _get_blob(token, repo, f"{_SESSIONS_FILE}.{i:03d}")
                if part is None:
                    break
                chunks.append(part)
                i += 1
            data = b"".join(chunks) if chunks else None
        if not data:
            print("Sessions restore skipped: no snapshot on GitHub", flush=True)
            return False
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = [n for n in zf.namelist() if n.endswith(".json") and _safe_name(n)]
            missing = [n for n in names if not os.path.exists(os.path.join(sessions_dir, n))]
            for n in missing:
                zf.extract(n, sessions_dir)
        if missing:
            print(f"Sessions restored from GitHub backup: {len(missing)} new files -> {sessions_dir}", flush=True)
            return True
        print("Sessions restore skipped: no new files in GitHub snapshot", flush=True)
        return False
    except Exception as e:
        print("Sessions restore skipped:", e, flush=True)
        return False


def backup_sessions(sessions_dir):
    """把 sessions 目录下的会话 JSON 打包上传到 db-snapshot 分支。返回是否成功。

    默认单文件 sessions.zip；超过 GitHub 单文件约 1MB 上限时分卷为
    sessions.zip.001/002… 上传（先删除旧单文件，避免恢复端读到过期快照）。
    """
    token, repo = _conf()
    if not enabled() or not os.path.isdir(sessions_dir):
        return False
    files = sorted(f for f in os.listdir(sessions_dir) if f.endswith(".json"))
    if not files:
        return True  # 无会话文件，没有需要备份的内容，不算失败
    try:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in files:
                zf.write(os.path.join(sessions_dir, f), os.path.basename(f))
        data = buf.getvalue()
        if len(data) <= _MAX_PART:
            _put_file(token, repo, _SESSIONS_FILE, data, "chore: sessions snapshot")
        else:
            _delete_if_exists(token, repo, _SESSIONS_FILE)
            parts = [data[i:i + _MAX_PART] for i in range(0, len(data), _MAX_PART)]
            for i, part in enumerate(parts, 1):
                _put_file(token, repo, f"{_SESSIONS_FILE}.{i:03d}", part,
                          f"chore: sessions snapshot part {i}/{len(parts)}")
        print(f"Sessions backed up to GitHub: {len(files)} files", flush=True)
        return True
    except Exception as e:
        print("Sessions backup failed:", e, flush=True)
        return False
