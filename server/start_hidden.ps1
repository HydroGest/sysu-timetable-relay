$ErrorActionPreference = 'Stop'

$server = Join-Path $PSScriptRoot 'timetable_server.py'
$py = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
if (-not $py) {
    $py = (Get-Command pyw.exe -ErrorAction SilentlyContinue).Source
}
if (-not $py) {
    Write-Error '找不到 pythonw.exe 或 pyw.exe'
    exit 1
}

if ($py -match 'pyw\.exe$') {
    Start-Process -FilePath $py -ArgumentList @('-3', ('"' + $server + '"')) -WindowStyle Hidden
} else {
    Start-Process -FilePath $py -ArgumentList @(('"' + $server + '"')) -WindowStyle Hidden
}
