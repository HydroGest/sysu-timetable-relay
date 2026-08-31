# SYSU 课表中继（sysu-timetable-relay）

把中山大学教务系统的登录态自动同步到本机常驻服务，再以简单 JSON API 把今日、明日和周课表提供给局域网内的物联网设备。

浏览器扩展（Edge / Chrome MV3）→ 读取教务系统 Cookie → 推送到本机服务 `127.0.0.1:8123` → 服务请求教务系统课表接口 → JSON API → 物联网设备。

## 目录

```text
sysu-timetable-relay/
├── server/
│   ├── timetable_server.py      # 托盘常驻课表中继服务
│   ├── start_hidden.vbs         # 隐藏窗口后台启动
│   └── install_autostart.ps1    # 写入 HKCU 开机自启
├── extension/
│   ├── manifest.json            # MV3 扩展
│   └── background.js            # 自动同步 Cookie
├── scripts/
│   └── allow_firewall.ps1       # 放行 TCP 8123（管理员）
├── requirements.txt
└── README.md
```

## 快速开始

### 1. 安装依赖

```powershell
cd D:\Users\Administrator\Documents\sysu-timetable-relay
python -m pip install -r requirements.txt
```

`pystray` 和 `Pillow` 用于托盘图标；没有安装时服务仍能运行，只是没有托盘菜单。

### 2. 启动服务

推荐双击 `server\start_hidden.vbs`，完全无窗口后台运行，没有控制台会一直占着任务栏。

调试时才用控制台方式：

```powershell
python server\timetable_server.py
```

托盘菜单里有“状态页”和“退出”（未安装 `pystray` 时没有托盘图标，但服务仍在运行）。

### 3. 加载浏览器扩展

打开扩展管理页：

- Edge：`edge://extensions`
- Chrome：`chrome://extensions`

打开“开发人员模式”，选择“加载解压的扩展”，然后选择本项目的 `extension` 文件夹。

扩展会自动读取 `jwxt.sysu.edu.cn` 和 `cas.sysu.edu.cn` 的 Cookie，在浏览器启动、教务页面加载完成时各推一次，之后每 5 分钟同步一次。

### 4. 验证

```powershell
curl http://127.0.0.1:8123/health
curl http://127.0.0.1:8123/today
curl http://127.0.0.1:8123/tomorrow
curl http://127.0.0.1:8123/week
curl "http://127.0.0.1:8123/timetable?week=1&day=1"
```

## 开机自启

```powershell
powershell -ExecutionPolicy Bypass -File server\install_autostart.ps1
```

写入的是当前用户的 `HKCU\...\Run` 键，不需要管理员权限。取消自启用 `-Remove` 参数：

```powershell
powershell -ExecutionPolicy Bypass -File server\install_autostart.ps1 -Remove
```

## 物联网设备访问

默认只监听 `127.0.0.1`，仅供本机使用。需要局域网设备访问时：

```powershell
python server\timetable_server.py --host 0.0.0.0
```

首次放行防火墙（管理员 PowerShell）：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\allow_firewall.ps1
```

之后设备访问 `http://<电脑IP>:8123/today` 即可。

## API

| 接口 | 说明 |
| --- | --- |
| `GET /health` | 服务状态；`session_ok` 表示是否已有 Cookie |
| `GET /today` | 今日课程 |
| `GET /tomorrow` | 明日课程 |
| `GET /week` | 今天对应的教学周 |
| `GET /timetable?week=N&day=today` | 指定周次和日期；`day` 支持 `today`、`tomorrow`、`1..7` |
| `POST /cookie` | 接收 Cookie（仅允许 127.0.0.1 / ::1），由扩展调用 |

返回示例：

```json
{
  "date": "2026-08-29",
  "week": 1,
  "weekday": 6,
  "classes": [
    {
      "section": 3,
      "time": "10:10~10:55",
      "course": "课程名",
      "teacher": "教师",
      "place": "教室"
    }
  ]
}
```

## 企业微信通知（WeCom）

relay 提供统一的企业微信通知接收与查询接口，采集端可以是 Android 通知转发 App、模拟器，或后续的 Windows 窗口监听器。

### 配置

首次运行会在 `server/wecom_config.json` 自动生成配置（模板见 `server/wecom_config.example.json`）。可配置项：

- `token`：写入接口的访问令牌，留空表示不校验；局域网开放时建议设置
- `allowed_groups` / `blocked_groups`：按群名子串过滤
- `allowed_keywords` / `blocked_keywords`：按群名、标题、正文子串过滤
- `max_events`：内存保留的最大事件数

### 接口

| 接口 | 说明 |
| --- | --- |
| `POST /wecom/events` | 接收通知事件（JSON） |
| `GET /wecom/latest` | 最近一条已通过过滤的事件 |
| `GET /wecom/list?limit=20` | 最近 N 条事件 |

`POST /wecom/events` 请求示例：

```json
{
  "source": "android",
  "group": "班级通知群",
  "sender": "辅导员",
  "title": "明天停课",
  "text": "明天上午课程暂停",
  "ts": "2026-08-29T10:00:00+08:00"
}
```

返回：

```json
{
  "accepted": true,
  "event": {
    "id": 1787972000000,
    "source": "android",
    "group": "班级通知群",
    "sender": "辅导员",
    "title": "明天停课",
    "text": "明天上午课程暂停",
    "ts": "2026-08-29T10:00:00+08:00"
  }
}
```

配置了 `token` 后，采集端用 `Authorization: Bearer <token>` 或请求体里的 `token` 字段。

### 采集端现状

企业微信 PC 端不发 Windows 原生 Toast，UI Automation 树为空，本地数据库加密，Windows 上没有稳定官方通道。推荐用 Android 手机或模拟器上的通知转发 App 把通知 POST 到这里；纯 Windows 的窗口钩子/OCR 方案仍在实验阶段。

想先验证 Windows 弹窗能不能读，可以运行：

```powershell
python server\wecom_win_probe.py --duration 60
```

保持脚本运行，在企业微信里给自己或任意群发一条消息，脚本会打印新出现/变化的顶层窗口。能稳定识别弹窗后，再决定是否做窗口钩子 + OCR。

### Android 转发示例

1. 手机或模拟器安装企业微信并登录，确认系统通知权限开启，企微设置里“显示消息内容”打开。
2. 用 Tasker + AutoNotification、MacroDroid 或任意“通知转发”App，监听企业微信（包名 `com.tencent.wework`）的通知。
3. 转发到 relay：

```json
{
  "source": "android",
  "group": "班级通知群",
  "sender": "辅导员",
  "title": "明天停课",
  "text": "明天上午课程暂停"
}
```

地址填 `http://<电脑IP>:8123/wecom/events`；如果 `wecom_config.json` 里设置了 `token`，加上 `Authorization: Bearer <token>`。

4. 服务端过滤由 `server/wecom_config.json` 控制；用 `GET /wecom/latest` 可立即检查是否收到。

## 选课抢课脚本（可选）

仓库里的 `scripts/grab_course.py` 封装了教务选课接口：

- `POST /choose-course-front-server/classCourseInfo/course/list`：查询可选课程
- `POST /choose-course-front-server/classCourseInfo/course/choose`：选课（先 `check:true`，遇到先修课检查再 `check:false` 确认）
- `POST /choose-course-front-server/classCourseInfo/course/back`：退课

用法：

```powershell
Copy-Item scripts\grab_targets.example.json targets.json
# 编辑 targets.json，填入你要抢的课程
python scripts\grab_course.py --targets targets.json --cookie "你的 Cookie"
```

Cookie 可以直接从浏览器 F12 -> Network 里复制，也可以用 relay 的 `server\cookies.txt`（`--cookie-file`）。

先确认目标能匹配到教学班，避免空跑：

```powershell
python scripts\grab_course.py --targets targets.json --list
```

`--list` 只查询并打印匹配到的教学班信息；`--dry-run` 只打印会发送的选课请求。两者都不会真正选课。

目标字段：

- `name`：显示名
- `courseName` / `courseNum`：在可选课程列表里匹配
- `clazzId`：可选，直接指定教学班 ID，跳过搜索
- `selectedType`：`1` 本专业、`2` 跨专业、`3` 体育、`4` 公选
- `selectedCate`：`11` 专必、`21` 专选、`30` 公选、`10` 公必

**注意**：教务系统明确提示使用插件抢课可能被锁号（错误码 `52021102` / `52021136`）。脚本默认 1.5 秒间隔加随机抖动，不要调低于 1 秒，不要在高峰期同时开多个实例。

## 安全说明

- `/cookie` 只接受来自本机的 POST，局域网其他设备不能覆盖你的 Cookie。
- Cookie 就是你的登录凭证。开启 `--host 0.0.0.0` 后，同一局域网的人可以读取课表，请只在可信网络使用。
- `server/cookies.txt` 保存原始 Cookie，已被 `.gitignore` 忽略，不要手动提交。
- 如果想改端口，先改 `extension/background.js` 里的 `SERVER`，再改 `manifest.json` 的 `host_permissions`，最后用 `--port` 启动服务。

## 已知限制

CAS 单点登录服务端有加密和风控，无法稳定做到完全免登录。本方案的定位是“浏览器登录一次，扩展持续同步”，物联网设备不直接登录教务系统。
