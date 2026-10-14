import time

import httpx


class LLMGateway:
    def __init__(self, cfg):
        self.cfg = cfg or {}

    @property
    def enabled(self):
        return bool(self.cfg.get("enabled") and self.cfg.get("base_url") and self.cfg.get("model"))

    def mode(self):
        return "llm_api" if self.enabled else "rule_engine"

    def complete(self, system, prompt):
        if not self.enabled:
            return None
        retries = int(self.cfg.get("retries", 2))
        timeout = float(self.cfg.get("timeout", 30))
        key = self.cfg.get("api_key", "")
        url = self.cfg["base_url"].rstrip("/") + "/chat/completions"
        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = "Bearer " + key
        payload = {
            "model": self.cfg["model"],
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "temperature": 0.3,
        }
        for attempt in range(retries + 1):
            try:
                with httpx.Client(timeout=timeout) as client:
                    r = client.post(url, json=payload, headers=headers)
                    r.raise_for_status()
                    data = r.json()
                    return data["choices"][0]["message"]["content"]
            except Exception:
                if attempt == retries:
                    return None
                time.sleep(0.6 * (attempt + 1))
        return None
