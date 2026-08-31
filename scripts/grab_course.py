"""中山大学教务系统选课脚本（抢课）。

基于选课前端使用的 choose-course-front-server 接口，只操作你自己的账号。

接口（base=https://jwxt.sysu.edu.cn/jwxt）：
  GET  /choose-course-front-server/classCourseInfo/selectCourseInfo
  POST /choose-course-front-server/classCourseInfo/course/list
  POST /choose-course-front-server/classCourseInfo/course/choose
  POST /choose-course-front-server/classCourseInfo/course/back

安全提醒：教务系统有抢课行为检测，请求过快会触发 52021102/52021136
（黑名单）。默认间隔 1.5 秒并带随机抖动，请勿盲目调小。
"""

import argparse
import json
import os
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE = "https://jwxt.sysu.edu.cn/jwxt"
SELECT_INFO_URL = "/choose-course-front-server/classCourseInfo/selectCourseInfo"
COURSE_LIST_URL = "/choose-course-front-server/classCourseInfo/course/list"
COURSE_CHOOSE_URL = "/choose-course-front-server/classCourseInfo/course/choose"
COURSE_BACK_URL = "/choose-course-front-server/classCourseInfo/course/back"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

# 这些错误继续抢没有意义
STOP_CODES = {
    "52021103",  # 不在选课范围内
    "52021133",  # 上课时间冲突
    "52021134",  # 跨校区课间跨度不足
    "52021135",  # 跨校区课间跨度不足
    "52021136",  # 黑名单
    "52021137",  # 每学期只能两门体育
    "52021138",  # 待筛选体育课超限
    "52021139",  # 已通过该课程
    "52021140",  # 未注册
    "52021141",  # 非本阶段不允许退课
    "52021144",  # 只能选一门校选选修
    "52021146",  # 该阶段不允许退课
    "52021147",  # 预置课程不允许退课
    "52021155",  # 考试时间冲突
    "52021158",  # 公共艺术只能一门
    "52021159",  # 已有公共艺术成绩
}


def load_cookie(args):
    cookie = args.cookie or os.environ.get("SYSU_COOKIE", "").strip()
    if not cookie and args.cookie_file:
        try:
            with open(args.cookie_file, "r", encoding="utf-8") as f:
                cookie = f.read().strip()
        except OSError as e:
            print(f"[cookie] 读取 {args.cookie_file} 失败: {e}")
    if not cookie:
        default_file = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "server", "cookies.txt"
        )
        if os.path.exists(default_file):
            try:
                with open(default_file, "r", encoding="utf-8") as f:
                    cookie = f.read().strip()
            except OSError:
                pass
    return cookie


def api(cookie, path, payload=None):
    url = BASE + path
    headers = {
        "User-Agent": UA,
        "Accept": "application/json, text/plain, */*",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": BASE + "/mk/courseSelection/",
    }
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if cookie:
        headers["Cookie"] = cookie
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data is not None else "GET")
    last_error = None
    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try:
                return json.loads(e.read().decode("utf-8"))
            except Exception:
                raise RuntimeError(f"HTTP {e.code} {e.reason}")
        except urllib.error.URLError as e:
            last_error = e
            if attempt < 3:
                time.sleep(1.5 * attempt)
    raise RuntimeError(f"网络错误: {last_error.reason}")


def get_stage(cookie):
    body = api(cookie, SELECT_INFO_URL)
    data = body.get("data")
    stage = data if isinstance(data, dict) else body
    if not stage.get("semesterYear") and str(stage.get("code")) != "200":
        raise RuntimeError(stage.get("message") or "选课阶段信息无效")
    return stage


def list_courses(cookie, stage, target, page_no, page_size):
    param = {
        "semesterYear": target.get("semesterYear") or stage.get("semesterYear") or "",
        "selectedType": target.get("selectedType", "1"),
        "selectedCate": target.get("selectedCate", "11"),
        "hiddenConflictStatus": target.get("hiddenConflictStatus", "0"),
        "hiddenSelectedStatus": target.get("hiddenSelectedStatus", "0"),
        "hiddenEmptyStatus": target.get("hiddenEmptyStatus", "0"),
        "vacancySortStatus": target.get("vacancySortStatus", "0"),
        "collectionStatus": target.get("collectionStatus", "0"),
    }
    body = api(cookie, COURSE_LIST_URL, {
        "pageNo": page_no,
        "pageSize": page_size,
        "param": param,
    })
    if str(body.get("code")) != "200":
        raise RuntimeError(body.get("message") or "课程列表查询失败")
    data = body.get("data")
    if not isinstance(data, dict):
        return [], 0
    rows = data.get("rows") or []
    return rows, data.get("total") or len(rows)


def matches(target, row):
    if target.get("courseNum"):
        if str(row.get("courseNum")) == str(target["courseNum"]):
            return True
    if target.get("courseName"):
        name = row.get("courseName") or ""
        if target["courseName"] in name or name in target["courseName"]:
            return True
    return False


def resolve_target(cookie, stage, target, page_size):
    if target.get("clazzId"):
        return {"clazzId": str(target["clazzId"]), "matched": None}
    best = None
    total = None
    for page in range(1, 21):
        rows, total = list_courses(cookie, stage, target, page, page_size)
        for row in rows:
            if not matches(target, row):
                continue
            if best is None:
                best = row
            elif (row.get("remainNum") or 0) > (best.get("remainNum") or 0):
                best = row
        if not rows or (total is not None and page * page_size >= total):
            break
    if best is None:
        return None
    return {
        "clazzId": str(best.get("teachingClassId") or best.get("clazzId") or ""),
        "matched": best,
    }


def choose(cookie, clazz_id, selected_type, selected_cate, check):
    payload = {
        "clazzId": clazz_id,
        "selectedType": selected_type,
        "selectedCate": selected_cate,
        "check": check,
    }
    return api(cookie, COURSE_CHOOSE_URL, payload)


def interpret(body):
    code = str(body.get("code") or "")
    data = body.get("data")
    message = body.get("message") or ""
    if code in STOP_CODES:
        return "stop", code, message
    if code in ("200", "52021104"):
        if isinstance(data, dict):
            return "precourse", code, "需要二次确认"
        text = data if isinstance(data, str) else message
        if any(k in text for k in ("成功", "等待筛选", "待筛选")):
            return "success", code, text
        if code == "52021104":
            return "success", code, "已选过该课程"
        return "unknown", code, text
    if code:
        return "retry", code, message
    return "retry", "?", message


def save_result(result, path="grab_result.json"):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print(f"[result] 保存失败: {e}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--targets", default="targets.json", help="目标课程 JSON")
    ap.add_argument("--cookie", default="", help="Cookie 请求头")
    ap.add_argument("--cookie-file", default="", help="从文件读取 Cookie")
    ap.add_argument("--interval", type=float, default=1.5, help="两次尝试间隔秒数（最小 1.0）")
    ap.add_argument("--timeout", type=float, default=3600, help="整体超时秒数")
    ap.add_argument("--once", action="store_true", help="每个目标只尝试一次")
    ap.add_argument("--dry-run", action="store_true", help="只打印请求，不发请求")
    ap.add_argument("--no-confirm", action="store_true", help="遇到先修课检查时不自动二次确认")
    ap.add_argument("--page-size", type=int, default=50)
    ap.add_argument("--result", default="grab_result.json")
    ap.add_argument("--list", action="store_true", help="只列出目标课程匹配到的教学班")
    args = ap.parse_args()

    interval = max(1.0, args.interval)
    try:
        with open(args.targets, "r", encoding="utf-8") as f:
            config = json.load(f)
    except OSError as e:
        print(f"[targets] 读取 {args.targets} 失败: {e}")
        sys.exit(1)
    targets = config.get("targets") or []
    if not targets:
        print("[targets] 没有目标课程")
        sys.exit(1)

    print("=" * 60)
    print("选课脚本已启动。系统有抢课检测，请勿把间隔调低于 1 秒。")
    print("=" * 60)

    if args.dry_run:
        for t in targets:
            print(json.dumps({
                "url": COURSE_CHOOSE_URL,
                "payload": {
                    "clazzId": t.get("clazzId", "<待解析>"),
                    "selectedType": t.get("selectedType", "1"),
                    "selectedCate": t.get("selectedCate", "11"),
                    "check": [True, False],
                },
            }, ensure_ascii=False))
        return

    cookie = load_cookie(args)
    if not cookie:
        print("[cookie] 未提供 Cookie。用 --cookie 或 --cookie-file，或设置 SYSU_COOKIE")
        sys.exit(1)

    stage = None
    for attempt in range(1, 6):
        try:
            stage = get_stage(cookie)
            break
        except Exception as e:
            print(f"[stage] 第 {attempt} 次获取选课阶段失败: {e}")
            if attempt < 5:
                time.sleep(3)
    if stage is None:
        print("[stage] 连续 5 次失败，退出")
        sys.exit(1)

    semester = stage.get("semesterYear") or ""
    print(f"[stage] 学期={semester} 阶段={stage.get('electiveCourseStageName') or '?'} "
          f"选课开关={stage.get('chooseCourseStatus') or '?'} 退课开关={stage.get('retreatCourseStatus') or '?'}")

    if args.list:
        keys = (
            "courseNum", "courseName", "teachingClassNum", "teachingClassName",
            "teachingClassId", "teachCourseId", "remainNum", "selectedStatus",
            "courseCateCode", "courseCate", "teachingTimePlace", "scheduleExamTime",
        )
        for t in targets:
            print(f"== {t.get('name')} ==")
            for page in range(1, 6):
                rows, total = None, 0
                for attempt in range(1, 4):
                    try:
                        rows, total = list_courses(cookie, stage, t, page, args.page_size)
                        break
                    except Exception as e:
                        print(f"[list] {t.get('name')} 第{page}页 第{attempt}次失败: {e}")
                        if attempt < 3:
                            time.sleep(2)
                if rows is None:
                    print(f"[list] {t.get('name')} 第{page}页 连续失败，跳过")
                    continue
                for row in rows:
                    if not t.get("courseName") and not t.get("courseNum"):
                        print(json.dumps({k: row.get(k) for k in keys}, ensure_ascii=False))
                    elif matches(t, row):
                        print(json.dumps({k: row.get(k) for k in keys}, ensure_ascii=False))
                if not rows or page * args.page_size >= total:
                    break
        return

    status = {t.get("name", i): {"status": "pending", "attempts": 0, "msg": ""} for i, t in enumerate(targets)}
    deadline = time.monotonic() + args.timeout

    try:
        while time.monotonic() < deadline:
            pending = [t for i, t in enumerate(targets) if status[t.get("name", i)]["status"] == "pending"]
            if not pending:
                break
            for t in pending:
                key = t.get("name", targets.index(t))
                if status[key]["status"] != "pending":
                    continue
                status[key]["attempts"] += 1
                try:
                    resolved = resolve_target(cookie, stage, t, args.page_size)
                except Exception as e:
                    print(f"[{time.strftime('%H:%M:%S')}] {key}: 解析教学班失败 {e}")
                    continue
                if resolved is None or not resolved["clazzId"]:
                    print(f"[{time.strftime('%H:%M:%S')}] {key}: 未在可选课程中找到")
                    continue
                if resolved["matched"]:
                    row = resolved["matched"]
                    print(f"[{time.strftime('%H:%M:%S')}] {key}: 匹配到 {row.get('courseNum')} "
                          f"{row.get('courseName')} 教学班 {row.get('teachingClassNum')} "
                          f"剩余 {row.get('remainNum')}")
                try:
                    body = choose(cookie, resolved["clazzId"], t.get("selectedType", "1"),
                                  t.get("selectedCate", "11"), True)
                except Exception as e:
                    print(f"[{time.strftime('%H:%M:%S')}] {key}: 请求失败 {e}")
                    continue
                state, code, msg = interpret(body)
                print(f"[{time.strftime('%H:%M:%S')}] {key}: code={code} {msg}")
                if state == "precourse":
                    if args.no_confirm:
                        print(f"[{time.strftime('%H:%M:%S')}] {key}: 需要二次确认，已跳过")
                        status[key] = {"status": "skipped", "attempts": status[key]["attempts"], "msg": "需要二次确认"}
                        continue
                    try:
                        body = choose(cookie, resolved["clazzId"], t.get("selectedType", "1"),
                                      t.get("selectedCate", "11"), False)
                        state, code, msg = interpret(body)
                        print(f"[{time.strftime('%H:%M:%S')}] {key}: 二次确认 code={code} {msg}")
                    except Exception as e:
                        print(f"[{time.strftime('%H:%M:%S')}] {key}: 二次确认失败 {e}")
                        continue
                if state == "success":
                    status[key] = {"status": "done", "attempts": status[key]["attempts"], "msg": msg}
                    print(f"[{time.strftime('%H:%M:%S')}] {key}: 成功")
                elif state == "stop":
                    status[key] = {"status": "aborted", "attempts": status[key]["attempts"], "msg": msg}
                    if code == "52021136":
                        print("检测到黑名单提示，立即停止。")
                        save_result({"targets": status}, args.result)
                        return
            if args.once:
                break
            time.sleep(interval * random.uniform(0.8, 1.5))
    except KeyboardInterrupt:
        print("\n手动中断")

    save_result({"targets": status}, args.result)
    summary = {k: v["status"] for k, v in status.items()}
    print("[summary]", json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
