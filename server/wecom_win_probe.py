"""企业微信 Windows 弹窗探查工具（只读）。

用于确认企业微信 PC 端的新消息弹窗能否被程序识别：
运行期间在企业微信里给自己或任意群发一条消息，脚本会打印新增/变化的
顶层窗口（类名、标题、可见性、位置）。此工具只读取窗口信息，
不改动企业微信的任何数据。
"""

import argparse
import ctypes
import datetime
import os
import sys
import time
from ctypes import wintypes

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

user32 = ctypes.windll.user32
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

MAX_PATH = 260
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

_name_cache = {}


def process_name(pid):
    if pid in _name_cache:
        return _name_cache[pid]
    name = None
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if handle:
        try:
            buf = ctypes.create_unicode_buffer(MAX_PATH)
            size = wintypes.DWORD(MAX_PATH)
            if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                name = os.path.basename(buf.value).lower()
        finally:
            kernel32.CloseHandle(handle)
    _name_cache[pid] = name
    return name


def window_info(hwnd):
    cls = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, cls, 256)
    length = user32.GetWindowTextLengthW(hwnd)
    title = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, title, length + 1)
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return {
        "hwnd": int(hwnd),
        "cls": cls.value,
        "title": title.value,
        "visible": bool(user32.IsWindowVisible(hwnd)),
        "rect": (rect.left, rect.top, rect.right, rect.bottom),
    }


def snapshot(targets):
    result = {}

    @WNDENUMPROC
    def callback(hwnd, _):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        name = process_name(pid.value)
        if name in targets:
            result[int(hwnd)] = window_info(hwnd)
        return True

    user32.EnumWindows(callback, 0)
    return result


def fmt(info):
    return (
        f"cls={info['cls']} visible={info['visible']} rect={info['rect']} "
        f"title={info['title']!r}"
    )


def now():
    return datetime.datetime.now().strftime("%H:%M:%S")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--duration", type=float, default=60, help="监控秒数")
    ap.add_argument("--interval", type=float, default=0.5, help="轮询间隔秒数")
    ap.add_argument(
        "--class-contains",
        default="",
        help="逗号分隔的类名子串，只输出匹配窗口",
    )
    args = ap.parse_args()

    needles = [x.strip() for x in args.class_contains.split(",") if x.strip()]

    def keep(info):
        return not needles or any(n in info["cls"] for n in needles)

    targets = {"wxwork.exe", "wxworkweb.exe"}
    print(
        f"[{now()}] targets={sorted(targets)} "
        f"duration={args.duration}s interval={args.interval}s"
    )
    print(f"[{now()}] initial windows:")
    initial = snapshot(targets)
    for hwnd, info in sorted(initial.items()):
        if keep(info):
            print(f"  {hwnd:#x} {fmt(info)}")

    previous = dict(initial)
    deadline = time.monotonic() + args.duration
    while time.monotonic() < deadline:
        time.sleep(args.interval)
        current = snapshot(targets)
        for hwnd, info in current.items():
            if not keep(info):
                continue
            if hwnd not in previous:
                print(f"[{now()}] NEW {hwnd:#x} {fmt(info)}")
                continue
            old = previous[hwnd]
            if info["visible"] and not old["visible"]:
                print(f"[{now()}] SHOW {hwnd:#x} {fmt(info)}")
            if info["title"] != old["title"]:
                print(f"[{now()}] TITLE {hwnd:#x} {fmt(info)}")
        for hwnd in set(previous) - set(current):
            if keep(previous[hwnd]):
                print(f"[{now()}] CLOSED {hwnd:#x} {fmt(previous[hwnd])}")
        previous = current
    print(f"[{now()}] done")


if __name__ == "__main__":
    main()
