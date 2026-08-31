import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import grab_course as g


def test_matches_by_name():
    assert g.matches({"courseName": "羽毛球"}, {"courseName": "羽毛球（提高班）"})
    assert not g.matches({"courseName": "篮球"}, {"courseName": "羽毛球（提高班）"})


def test_matches_by_num():
    assert g.matches({"courseNum": "MA111"}, {"courseNum": "MA111"})
    assert not g.matches({"courseNum": "MA111"}, {"courseNum": "MA112"})


def test_interpret_success():
    state, code, msg = g.interpret({"code": "200", "data": "选课成功!"})
    assert state == "success"
    state, code, msg = g.interpret({"code": "52021104", "data": ""})
    assert state == "success"


def test_interpret_precourse():
    state, code, msg = g.interpret({"code": "200", "data": {"rows": []}})
    assert state == "precourse"


def test_interpret_stop_blacklist():
    state, code, msg = g.interpret({"code": "52021136", "message": "黑名单"})
    assert state == "stop"


if __name__ == "__main__":
    for fn in (test_matches_by_name, test_matches_by_num, test_interpret_success,
               test_interpret_precourse, test_interpret_stop_blacklist):
        fn()
        print(f"{fn.__name__}: OK")
    print("all tests passed")
