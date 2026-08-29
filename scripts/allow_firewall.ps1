# 以管理员身份运行，放行 TCP 8123 入站（专用网络）
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator
)
if (-not $isAdmin) {
    Write-Warning "请以管理员身份运行"
    exit 1
}

New-NetFirewallRule `
    -DisplayName "SYSU Timetable Relay" `
    -Direction Inbound `
    -Protocol TCP `
    -LocalPort 8123 `
    -Action Allow `
    -Profile Private `
    -ErrorAction SilentlyContinue

Write-Host "已放行 TCP 8123（专用网络）"
