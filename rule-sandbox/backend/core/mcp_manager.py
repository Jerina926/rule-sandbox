import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import asyncio
import json
import time
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPManager:
    def __init__(self, cfg):
        self.cfg = cfg
        self._sessions = {}
        self._stacks = {}
        self._lock = asyncio.Lock()
        self.status = {}

    def _server_cfg(self, name):
        return (self.cfg.get("mcp", {}).get("servers") or {})[name]

    def _params(self, name):
        entry = self._server_cfg(name)
        cmd = entry["command"].replace("{python}", sys.executable)
        return StdioServerParameters(command=cmd, args=list(entry.get("args", [])))

    def configured(self):
        return list((self.cfg.get("mcp", {}).get("servers") or {}).keys())

    def is_connected(self, name):
        return name in self._sessions

    async def connect(self, name):
        async with self._lock:
            if name in self._sessions:
                return True
            try:
                stack = AsyncExitStack()
                read, write = await stack.enter_async_context(stdio_client(self._params(name)))
                session = await stack.enter_async_context(ClientSession(read, write))
                await asyncio.wait_for(session.initialize(),
                                       float(self.cfg.get("mcp", {}).get("startup_timeout", 30)))
                self._stacks[name] = stack
                self._sessions[name] = session
                self.status[name] = {"connected": True, "error": ""}
                return True
            except Exception as e:
                self.status[name] = {"connected": False, "error": str(e)}
                try:
                    await stack.aclose()
                except Exception:
                    pass
                return False

    async def connect_all(self):
        results = {}
        for name in self.configured():
            results[name] = await self.connect(name)
        return results

    @staticmethod
    def _payload(result):
        sc = getattr(result, "structured_content", None)
        if isinstance(sc, dict):
            if isinstance(sc.get("result"), (dict, list)):
                return sc["result"]
            if sc:
                return sc
        for item in getattr(result, "content", []) or []:
            text = getattr(item, "text", None)
            if text:
                try:
                    return json.loads(text)
                except Exception:
                    continue
        return None

    async def call_tool(self, server, tool, args):
        retries = int(self.cfg.get("mcp", {}).get("retries", 2))
        timeout = float(self.cfg.get("mcp", {}).get("call_timeout", 60))
        last_err = None
        for attempt in range(retries + 1):
            session = self._sessions.get(server)
            if session is None:
                ok = await self.connect(server)
                session = self._sessions.get(server)
                if not ok:
                    last_err = "server not connected"
                    break
            try:
                res = await asyncio.wait_for(session.call_tool(tool, arguments=args), timeout)
                if getattr(res, "isError", False):
                    raise RuntimeError("tool error: %s" % res.content)
                return self._payload(res), attempt, None
            except Exception as e:
                last_err = str(e)
                if server in self._sessions:
                    await self._drop(server)
                if attempt < retries:
                    await asyncio.sleep(0.5 * (attempt + 1))
        return None, retries, last_err

    async def _drop(self, name):
        self._sessions.pop(name, None)
        stack = self._stacks.pop(name, None)
        if stack:
            try:
                await stack.aclose()
            except Exception:
                pass
        self.status[name] = {"connected": False, "error": "dropped"}

    async def list_tools(self, server):
        session = self._sessions.get(server)
        if session is None:
            return None
        try:
            res = await asyncio.wait_for(session.list_tools(), 15)
            return [t.name for t in res.tools]
        except Exception:
            return None

    async def close_all(self):
        for name in list(self._stacks.keys()):
            await self._drop(name)

    async def reload(self, new_cfg):
        await self.close_all()
        self.cfg = new_cfg
        return await self.connect_all()
