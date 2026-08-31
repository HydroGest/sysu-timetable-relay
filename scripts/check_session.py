"""检查 relay 保存的 Cookie 是否包含有效的教务会话。"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import grab_course as g

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cookie", default="")
    ap.add_argument("--cookie-file", default="")
    args = ap.parse_args()

    cookie = g.load_cookie(args)
    if not cookie:
        print("没有找到 Cookie")
        sys.exit(1)

    names = [p.split("=", 1)[0].strip() for p in cookie.split(";") if p.strip()]
    print("cookie 字段:", ", ".join(names))

    ok = False
    try:
        stage = g.get_stage(cookie)
        print("selectCourseInfo:", json.dumps(stage, ensure_ascii=False)[:500])
        ok = bool(stage.get("semesterYear") or stage.get("code") == "200")
    except Exception as e:
        print("selectCourseInfo 失败:", e)

    try:
        login = g.api(cookie, "/api/login/status")
        print("login/status:", json.dumps(login, ensure_ascii=False)[:300])
    except Exception as e:
        print("login/status 失败:", e)

    if ok:
        print("会话有效")
        return
    print("会话无效：缺少教务系统会话 Cookie，请在扩展浏览器里打开 jwxt 学生首页并点扩展图标同步")
    sys.exit(1)


if __name__ == "__main__":
    main()
