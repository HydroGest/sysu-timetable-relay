import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import grab_course as g

calls = []


def fake_api(cookie, path, payload=None):
    calls.append((path, payload))
    if path == g.SELECT_INFO_URL:
        return {
            "code": "200",
            "data": {
                "code": "200",
                "enrolmentCode": "",
                "semesterYear": "2026-1",
                "electiveCourseStageName": "第三阶段",
                "chooseCourseStatus": "1",
                "retreatCourseStatus": "0",
            },
        }
    if path == g.COURSE_LIST_URL:
        return {
            "code": "200",
            "data": {
                "total": 1,
                "rows": [{
                    "courseNum": "MA111",
                    "courseName": "高级语言程序设计",
                    "teachingClassId": "T1",
                    "teachingClassNum": "01",
                    "remainNum": 5,
                    "selectedStatus": "0",
                }],
            },
        }
    if path == g.COURSE_CHOOSE_URL:
        if payload and payload.get("check") is True:
            return {"code": "200", "data": {"rows": []}}
        return {"code": "200", "data": "选课成功!"}
    raise AssertionError(path)


def main():
    g.api = fake_api
    stage = g.get_stage("cookie")
    assert stage["semesterYear"] == "2026-1"

    target = {
        "name": "高级语言程序设计",
        "courseNum": "MA111",
        "selectedType": "1",
        "selectedCate": "11",
    }
    resolved = g.resolve_target("cookie", stage, target, 50)
    assert resolved["clazzId"] == "T1"

    body = g.choose("cookie", resolved["clazzId"], "1", "11", True)
    state, code, msg = g.interpret(body)
    assert state == "precourse"

    body = g.choose("cookie", resolved["clazzId"], "1", "11", False)
    state, code, msg = g.interpret(body)
    assert state == "success"

    choose_calls = [p for path, p in calls if path == g.COURSE_CHOOSE_URL]
    assert choose_calls[0]["check"] is True
    assert choose_calls[1]["check"] is False
    assert choose_calls[0]["clazzId"] == "T1"
    print("integration test passed")


if __name__ == "__main__":
    main()
