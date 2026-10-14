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
            with open(path, encoding="utf-8") as f:
                return json.load(f)

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
        doc = self.get(sid)
        if doc is None:
            doc = self.create()
            sid = doc["session_id"]
        doc["runs"].append({
            "run_index": len(doc["runs"]) + 1,
            "at": _now(),
            "request": request,
            "result": result,
        })
        doc["updated_at"] = _now()
        with self.lock:
            with open(self._path(sid), "w", encoding="utf-8") as f:
                json.dump(doc, f, ensure_ascii=False, indent=1)
        return doc


def _now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
