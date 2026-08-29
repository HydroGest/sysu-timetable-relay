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

```powershell
python server\timetable_server.py
```

也可以双击 `server\start_hidden.vbs` 隐藏后台运行。托盘菜单里有“状态页”和“退出”。

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

## 安全说明

- `/cookie` 只接受来自本机的 POST，局域网其他设备不能覆盖你的 Cookie。
- Cookie 就是你的登录凭证。开启 `--host 0.0.0.0` 后，同一局域网的人可以读取课表，请只在可信网络使用。
- `server/cookies.txt` 保存原始 Cookie，已被 `.gitignore` 忽略，不要手动提交。
- 如果想改端口，先改 `extension/background.js` 里的 `SERVER`，再改 `manifest.json` 的 `host_permissions`，最后用 `--port` 启动服务。

## 已知限制

CAS 单点登录服务端有加密和风控，无法稳定做到完全免登录。本方案的定位是“浏览器登录一次，扩展持续同步”，物联网设备不直接登录教务系统。
