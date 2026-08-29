param(
    [switch]$Remove
)

$key = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
$name = 'SysuTimetableRelay'
$vbs = Join-Path $PSScriptRoot 'start_hidden.vbs'

if ($Remove) {
    Remove-ItemProperty -Path $key -Name $name -ErrorAction SilentlyContinue
    Write-Host "已移除开机自启: $name"
    return
}

if (-not (Test-Path $vbs)) {
    Write-Error "找不到 start_hidden.vbs: $vbs"
    exit 1
}

Set-ItemProperty -Path $key -Name $name -Value "wscript.exe `"$vbs`""
Write-Host "已写入开机自启: $name"
Write-Host "重启后生效；也可立即双击运行: $vbs"
