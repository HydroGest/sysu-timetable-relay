"""企业微信通知事件存储与过滤。"""

import datetime
import json
import os
import threading
import time

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wecom_config.json")

DEFAULTS = {
    "token": "",
    "allowed_groups": [],
    "blocked_groups": [],
    "allowed_keywords": [],
    "blocked_keywords": [],
    "max_events": 200,
}


class WeComStore:
    def __init__(self, config_file=CONFIG_FILE):
        self.config_file = config_file
        self.config = dict(DEFAULTS)
        self.events = []
        self.lock = threading.Lock()
        self._load()

    def _load(self):
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            for key in DEFAULTS:
                if key in data:
                    self.config[key] = data[key]
        except FileNotFoundError:
            self._save()
        except Exception:
            pass

    def _save(self):
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def count(self):
        with self.lock:
            return len(self.events)

    def authorize(self, token):
        expected = self.config.get("token", "")
        return not expected or (token or "") == expected

    def _contains_any(self, text, needles):
        return any(n and n in text for n in needles)

    def _matches(self, group, title, text):
        cfg = self.config
        haystack = " ".join(x for x in (group or "", title or "", text or "") if x)
        if cfg.get("blocked_groups") and self._contains_any(group or "", cfg.get("blocked_groups")):
            return False
        if cfg.get("allowed_groups") and not self._contains_any(group or "", cfg.get("allowed_groups")):
            return False
        if cfg.get("blocked_keywords") and self._contains_any(haystack, cfg.get("blocked_keywords")):
            return False
        if cfg.get("allowed_keywords") and not self._contains_any(haystack, cfg.get("allowed_keywords")):
            return False
        return True

    def ingest(self, payload):
        group = str(payload.get("group") or payload.get("chat") or "").strip()
        sender = str(payload.get("sender") or payload.get("from") or "").strip()
        title = str(payload.get("title") or "").strip()
        text = str(payload.get("text") or payload.get("body") or "").strip()
        if not (group or title or text):
            return None, "empty"
        if not self._matches(group, title, text):
            return None, "filtered"
        event = {
            "id": int(time.time() * 1000),
            "source": str(payload.get("source") or "unknown"),
            "group": group,
            "sender": sender,
            "title": title,
            "text": text,
            "ts": str(
                payload.get("ts")
                or datetime.datetime.now().astimezone().isoformat(timespec="seconds")
            ),
        }
        with self.lock:
            self.events.append(event)
            max_events = int(self.config.get("max_events", 200) or 200)
            if len(self.events) > max_events:
                self.events = self.events[-max_events:]
        return event, "accepted"

    def latest(self):
        with self.lock:
            return self.events[-1] if self.events else None

    def list(self, limit=20):
        try:
            limit = max(1, int(limit))
        except Exception:
            limit = 20
        with self.lock:
            return list(reversed(self.events[-limit:]))
