"""公开数据源实时拉取：对用户选定的官方数据源 URL 发起 GET，
提取页面文本中的代表性百分比（中位数），用于指标校准。
任何失败（超时/反爬/无百分数/网络错误）都返回 ok=False，由上层回退预设校准基线。
"""
import asyncio
import re
import time

import httpx

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

_PCT = re.compile(r"(\d+(?:\.\d+)?)\s*%")


def _extract_pct(text):
    vals = []
    for m in _PCT.finditer(text or ""):
        try:
            v = float(m.group(1))
        except ValueError:
            continue
        if 0 <= v <= 100:
            vals.append(v)
    if not vals:
        return None
    vals.sort()
    return vals[len(vals) // 2]


def live_fetch(url, timeout=5.0):
    t0 = time.time()
    try:
        r = httpx.get(url, timeout=timeout, follow_redirects=True,
                      headers={"User-Agent": UA}, verify=False)
        ms = int((time.time() - t0) * 1000)
        if r.status_code != 200:
            return {"ok": False, "status": r.status_code, "ms": ms}
        pct = _extract_pct(r.text)
        if pct is None:
            return {"ok": False, "status": r.status_code, "reason": "no_percent_found", "ms": ms}
        return {"ok": True, "value": pct, "url": url, "ms": ms}
    except Exception as e:
        return {"ok": False, "error": str(e)[:160], "ms": int((time.time() - t0) * 1000)}


async def try_live_fetch(url, timeout=5.0):
    if not url or not url.startswith(("http://", "https://")):
        return {"ok": False, "reason": "no_url", "ms": 0}
    try:
        return await asyncio.to_thread(live_fetch, url, timeout)
    except Exception as e:
        return {"ok": False, "error": str(e)[:160], "ms": 0}
