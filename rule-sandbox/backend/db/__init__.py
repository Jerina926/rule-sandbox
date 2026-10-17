"""SQLite 数据库入口与配置工具。

特性：
- WAL 模式（提高并发读写性能，避免读阻塞写）
- check_same_thread=False（FastAPI 多线程安全）
- 路径可通过环境变量 RSB_DB_PATH 覆盖（云端默认 ./data/rule_sandbox.db）
- 启动时自动 init_schema
"""
import os
import sqlite3
import threading
from contextlib import contextmanager

DEFAULT_DB_PATH = os.path.join(
    os.environ.get("RSB_DATA_DIR", os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "data", "rule_sandbox.db",
)


def resolve_db_path():
    """优先级：env RSB_DB_PATH > env RSB_DATA_DIR + data/rule_sandbox.db > 默认 ./data/rule_sandbox.db"""
    p = os.environ.get("RSB_DB_PATH", "").strip()
    if p:
        return p
    data_dir = os.environ.get("RSB_DATA_DIR", "").strip()
    if not data_dir:
        data_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    return os.path.join(data_dir, "data", "rule_sandbox.db")


_db_lock = threading.Lock()
_conn = None


def init_schema(db_path=None):
    """读取 schema.sql 并执行 CREATE TABLE IF NOT EXISTS."""
    db_path = db_path or resolve_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path, encoding="utf-8") as f:
        schema_sql = f.read()
    with sqlite3.connect(db_path) as conn:
        conn.executescript(schema_sql)
        conn.commit()
    return db_path


def get_conn(db_path=None):
    """获取单例连接。FastAPI 多线程下共用一个连接不安全，本函数用本地锁 + check_same_thread=False。"""
    global _conn
    with _db_lock:
        if _conn is None:
            db_path = db_path or resolve_db_path()
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            _conn = sqlite3.connect(db_path, check_same_thread=False, isolation_level=None)
            _conn.row_factory = sqlite3.Row
            _conn.execute("PRAGMA journal_mode=WAL")
            _conn.execute("PRAGMA synchronous=NORMAL")
            _conn.execute("PRAGMA foreign_keys=ON")
        return _conn


def close_conn():
    global _conn
    with _db_lock:
        if _conn is not None:
            _conn.close()
            _conn = None


@contextmanager
def tx():
    """事务上下文。"""
    conn = get_conn()
    with _db_lock:
        try:
            conn.execute("BEGIN")
            yield conn
            conn.execute("COMMIT")
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
            raise


def row_to_dict(row):
    return {k: row[k] for k in row.keys()} if row else None


def rows_to_list(rows):
    return [row_to_dict(r) for r in rows]
