import datetime
import json
import os
import threading
import uuid


class SessionStore:
    def __init__(self, directory):
        self.dir = directory
        os.makedirs(self.dir, exist_ok=True)
        self.lock = threading.Lock()

    def _path(self, sid):
        return os.path.join(self.dir, "%s.json" % sid)

    def _load(self, path):
        """无锁读取单个会话文件（调用方需自行持锁）。"""
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def create(self):
        sid = uuid.uuid4().hex[:12]
        with self.lock:
            doc = {"session_id": sid, "created_at": _now(), "runs": []}
            with open(self._path(sid), "w", encoding="utf-8") as f:
                json.dump(doc, f, ensure_ascii=False, indent=1)
        return doc

    def get(self, sid):
        path = self._path(sid)
        if not os.path.exists(path):
            return None
        with self.lock:
            return self._load(path)

    def list_sessions(self):
        out = []
        for fn in sorted(os.listdir(self.dir)):
            if not fn.endswith(".json"):
                continue
            doc = self.get(fn[:-5])
            if doc:
                out.append({
                    "session_id": doc["session_id"],
                    "created_at": doc["created_at"],
                    "runs": len(doc["runs"]),
                    "last_content": doc["runs"][-1]["request"]["content"] if doc["runs"] else "",
                    "last_society": doc["runs"][-1]["request"]["society_id"] if doc["runs"] else "",
                })
        return out

    def add_run(self, sid, request, result):
        # 读-改-写全程持锁：并发下不会因「读到旧 doc → 另一线程已写入 → 覆盖丢 run」而丢失记录
        # （旧实现 get→修改→写 分三段加锁，存在竞态窗口）
        with self.lock:
            path = self._path(sid)
            doc = self._load(path) if os.path.exists(path) else None
            if doc is None:
                sid = uuid.uuid4().hex[:12]
                doc = {"session_id": sid, "created_at": _now(), "runs": []}
            doc["runs"].append({
                "run_index": len(doc["runs"]) + 1,
                "at": _now(),
                "request": request,
                "result": result,
            })
            doc["updated_at"] = _now()
            with open(self._path(sid), "w", encoding="utf-8") as f:
                json.dump(doc, f, ensure_ascii=False, indent=1)
        return doc


def _now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")