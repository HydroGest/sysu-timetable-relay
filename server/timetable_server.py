"""中山大学课表中继服务（托盘常驻版）。

浏览器扩展把教务系统 Cookie 推送到 http://127.0.0.1:8123/cookie，
本服务缓存并对外提供：
  /today  /tomorrow  /week  /timetable?week=N&day=today  /health

运行：
  pip install -r requirements.txt
  python timetable_server.py            # 默认 127.0.0.1:8123，仅本机
  python timetable_server.py --host 0.0.0.0 --port 8123   # 局域网设备可访问

建议用 pythonw 或 start_hidden.vbs 后台运行；装有 pystray 时显示托盘图标。
"""

import argparse
import datetime
import json
import os
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from wecom import WeComStore


BASE = "https://jwxt.sysu.edu.cn/jwxt"
QUERY_URL = BASE + "/timetable-search/stuTimeTabPrint/studentQuery"
CALENDER_URL = BASE + "/base-info/school-calender"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
COOKIE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies.txt")


class Session:
    def __init__(self):
        self.acad_year = "2026-1"
        self._cookie = os.environ.get("SYSU_COOKIE", "").strip()
        self._load_file()
        self.cache = {}
        self.lock = threading.Lock()

    def _load_file(self):
        try:
            with open(COOKIE_FILE, "r", encoding="utf-8") as f:
                data = f.read().strip()
            if data:
                self._cookie = data
        except Exception:
            pass

    def set_cookie(self, cookie):
        self._cookie = (cookie or "").strip()
        try:
            with open(COOKIE_FILE, "w", encoding="utf-8") as f:
                f.write(self._cookie)
        except Exception:
            pass

    def cookie(self):
        return self._cookie

    def _headers(self, data=None):
        h = {"User-Agent": UA, "Referer": "https://jwxt.sysu.edu.cn/jwxt/mk/schedule-web/"}
        c = self.cookie()
        if c:
            h["Cookie"] = c
        if data is not None:
            h["Content-Type"] = "application/json"
        return h

    def _post(self, url, payload):
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=body, headers=self._headers(body), method="POST")
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))

    def _get(self, url):
        req = urllib.request.Request(url, headers=self._headers())
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8"))

    def week_of(self, date):
        for w in range(1, 26):
            try:
                resp = self._get(CALENDER_URL + "?" + urllib.parse.urlencode({
                    "academicYear": self.acad_year, "weekly": w
                }))
            except Exception:
                continue
            if resp.get("code") != 200:
                continue
            d = resp.get("data") or {}
            try:
                start = datetime.date.fromisoformat(d["startTime"])
                end = datetime.date.fromisoformat(d["endTime"])
            except Exception:
                continue
            if start <= date <= end:
                return w
        return None

    def fetch(self, week):
        with self.lock:
            hit = self.cache.get(week)
            if hit and time.time() - hit["ts"] < 1800:
                return hit["data"]
        data = self._post(QUERY_URL, {
            "acadYear": self.acad_year,
            "submitFlag": "1",
            "week": str(week),
            "nothroughCourseFlag": "1",
        })
        if data.get("code") != 200:
            raise RuntimeError(data.get("msg") or "query failed")
        with self.lock:
            self.cache[week] = {"ts": time.time(), "data": data["data"]}
        return data["data"]

    def day_classes(self, date):
        week = self.week_of(date)
        if week is None:
            return None
        data = self.fetch(week)
        timetable = data.get("timetable", {})
        rows = []
        for sec in range(1, 12):
            for item in timetable.get(f"{date.isoweekday()}{sec}") or []:
                if item.get("emptyFlag"):
                    continue
                rows.append({
                    "section": sec,
                    "time": item.get("timeDetail", ""),
                    "course": item.get("courseName", ""),
                    "teacher": item.get("teachingStaffName", ""),
                    "place": item.get("classPlace", ""),
                })
        return {"date": str(date), "week": week, "weekday": date.isoweekday(), "classes": rows}


S = Session()
WECOM = WeComStore()


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, obj, cors=True):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if cors:
            self._cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors_headers()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _client_is_local(self):
        return self.client_address[0] in ("127.0.0.1", "::1")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/wecom/events":
            self._wecom_events()
            return
        if parsed.path != "/cookie":
            self._send(404, {"error": "not found"})
            return
        if not self._client_is_local():
            self._send(403, {"error": "local only"})
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            cookie = data.get("cookie", "")
            if cookie:
                S.set_cookie(cookie)
                self._send(200, {"ok": True})
            else:
                self._send(400, {"error": "empty cookie"})
        except Exception as e:
            self._send(400, {"error": str(e)})

    def _wecom_events(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception as e:
            self._send(400, {"error": f"bad json: {e}"})
            return
        auth = (self.headers.get("Authorization") or "").removeprefix("Bearer ").strip()
        token = auth or str(data.get("token") or "")
        if not WECOM.authorize(token):
            self._send(403, {"error": "forbidden"})
            return
        event, reason = WECOM.ingest(data)
        if event is None:
            code = 400 if reason == "empty" else 200
            self._send(code, {"accepted": False, "reason": reason})
            return
        self._send(200, {"accepted": True, "event": event})

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(parsed.query)
        path = parsed.path
        today = datetime.date.today()
        try:
            if path == "/health":
                self._send(200, {
                    "ok": True,
                    "session_ok": bool(S.cookie()),
                    "wecom_events": WECOM.count(),
                })
                return
            if path == "/wecom/latest":
                self._send(200, {"event": WECOM.latest()})
                return
            if path == "/wecom/list":
                limit = int((q.get("limit") or ["20"])[0])
                self._send(200, {"events": WECOM.list(limit)})
                return
            if path == "/today":
                self._send(200, S.day_classes(today))
                return
            if path == "/tomorrow":
                self._send(200, S.day_classes(today + datetime.timedelta(days=1)))
                return
            if path == "/week":
                self._send(200, {"date": str(today), "week": S.week_of(today)})
                return
            if path == "/timetable":
                week = int((q.get("week") or [str(S.week_of(today) or 1)])[0])
                day = (q.get("day") or ["today"])[0]
                if day == "today":
                    date = today
                elif day == "tomorrow":
                    date = today + datetime.timedelta(days=1)
                else:
                    date = today + datetime.timedelta(days=(int(day) - today.isoweekday()))
                self._send(200, S.day_classes(date))
                return
        except Exception as e:
            msg = "session_expired" if "401" in str(e) or "HTTP Error 401" in str(e) else str(e)
            self._send(502, {"error": msg})
            return
        self._send(404, {"error": "not found"})

    def log_message(self, fmt, *args):
        pass


def run_server(host, port):
    srv = ThreadingHTTPServer((host, port), Handler)
    print(f"listening on http://{host}:{port}")
    srv.serve_forever()


def run_tray(host, port):
    try:
        import pystray
        from PIL import Image
    except Exception:
        return False

    def open_status():
        import webbrowser
        webbrowser.open(f"http://127.0.0.1:{port}/health")

    def quit_app(icon, item):
        icon.stop()
        os._exit(0)

    img = Image.new("RGB", (32, 32), (70, 130, 220))
    menu = pystray.Menu(
        pystray.MenuItem("状态页", open_status),
        pystray.MenuItem("退出", quit_app),
    )
    icon = pystray.Icon("sysu-timetable", img, "SYSU 课表中继", menu)
    icon.run()
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8123)
    ap.add_argument("--acad-year", default="2026-1")
    ap.add_argument("--cookie", default="", help="初始 Cookie 请求头（可选，扩展会自动同步）")
    args = ap.parse_args()
    S.acad_year = args.acad_year
    if args.cookie:
        S.set_cookie(args.cookie)

    t = threading.Thread(target=run_server, args=(args.host, args.port), daemon=True)
    t.start()
    if not run_tray(args.host, args.port):
        while True:
            time.sleep(3600)


if __name__ == "__main__":
    main()
