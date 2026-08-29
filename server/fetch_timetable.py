"""中山大学教务系统课表 API 客户端（只读取，不改动选课）。

用法：
  1. 在浏览器登录教务系统，F12 -> Network 里找到任意请求，复制 Cookie 请求头；
  2. 设置环境变量 SYSU_COOKIE，或运行参数 --cookie "xxx";
  3. 运行：python fetch_timetable.py --acad-year 2026-1 --week auto

默认输出今天和明天的课程；--day today|tomorrow|1..7 可指定。
"""

import argparse
import datetime
import json
import os
import sys
import urllib.parse
import urllib.request


BASE = "https://jwxt.sysu.edu.cn/jwxt"
QUERY_URL = BASE + "/timetable-search/stuTimeTabPrint/studentQuery"
CALENDER_URL = BASE + "/base-info/school-calender"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"


def get_cookie(args):
    return args.cookie or os.environ.get("SYSU_COOKIE", "").strip()


def _headers(cookie, json_body=False):
    h = {
        "User-Agent": UA,
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://jwxt.sysu.edu.cn/jwxt/mk/schedule-web/",
        "Cookie": cookie,
    }
    if json_body:
        h["Content-Type"] = "application/json"
    return h


def request_json(url, cookie, data=None):
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(
        url, data=body, headers=_headers(cookie, json_body=data is not None), method="POST" if data is not None else "GET"
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def query_timetable(cookie, acad_year, week):
    payload = {
        "acadYear": acad_year,
        "submitFlag": "1",
        "week": str(week),
        "nothroughCourseFlag": "1",
    }
    resp = request_json(QUERY_URL, cookie, payload)
    if resp.get("code") != 200:
        raise RuntimeError(f"查询失败: code={resp.get('code')} msg={resp.get('msg')}")
    return resp["data"]


def week_of_today(cookie, acad_year):
    today = datetime.date.today()
    for w in range(1, 26):
        try:
            resp = request_json(CALENDER_URL + "?" + urllib.parse.urlencode({
                "academicYear": acad_year, "weekly": w
            }), cookie)
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
        if start <= today <= end:
            return w
    return None


def parse_day(timetable, day):
    rows = []
    for sec in range(1, 12):
        cells = timetable.get(f"{day}{sec}")
        if not cells:
            continue
        for item in cells:
            if item.get("emptyFlag"):
                continue
            rows.append({
                "节次": sec,
                "时间": item.get("timeDetail", ""),
                "课程": item.get("courseName", ""),
                "教师": item.get("teachingStaffName", ""),
                "地点": item.get("classPlace", ""),
            })
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cookie", default="", help="Cookie 请求头字符串")
    ap.add_argument("--acad-year", default="2026-1", help="学年学期，如 2026-1")
    ap.add_argument("--week", default="auto", help="周次，auto 表示按今天自动推算")
    ap.add_argument("--day", default="today", help="today / tomorrow / 1-7")
    args = ap.parse_args()

    cookie = get_cookie(args)
    if not cookie:
        print("请先提供 Cookie：设置环境变量 SYSU_COOKIE 或使用 --cookie")
        sys.exit(1)

    week = args.week
    if week == "auto":
        week = week_of_today(cookie, args.acad_year)
        if week is None:
            print("无法自动推算当前周次，请用 --week 指定")
            sys.exit(1)

    data = query_timetable(cookie, args.acad_year, week)
    timetable = data.get("timetable", {})

    today = datetime.date.today()
    day_map = {
        "today": today.isoweekday(),
        "tomorrow": (today + datetime.timedelta(days=1)).isoweekday(),
    }
    if args.day in day_map:
        day = day_map[args.day]
        label = args.day
    else:
        day = int(args.day)
        label = f"星期{day}"

    rows = parse_day(timetable, day)
    print(f"学年学期 {args.acad_year}  第 {week} 周  {label}")
    if not rows:
        print("（当天没有课）")
        return
    for r in sorted(rows, key=lambda x: x["节次"]):
        print(f"{r['节次']:>2}节 {r['时间']:<16} {r['课程']}  {r['教师']}  {r['地点']}")


if __name__ == "__main__":
    main()
