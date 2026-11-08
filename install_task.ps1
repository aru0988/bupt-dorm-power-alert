param([switch]$Unregister)

$ErrorActionPreference = "Stop"
$TaskName = "DormPowerAlert"
$Base = $PSScriptRoot
$Script = Join-Path $Base "dorm_alert.py"

if ($Unregister) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "已删除任务：$TaskName"
    return
}

$PyLauncher = (Get-Command py.exe -ErrorAction SilentlyContinue).Source
if ($PyLauncher) {
    $Exe = $PyLauncher
    $ArgLine = '-3.10 "' + $Script + '"'
} else {
    $Exe = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
    if (-not $Exe) { throw "找不到 Python，请先安装 Python 3.10" }
    $ArgLine = '"' + $Script + '"'
}

$Action = New-ScheduledTaskAction -Execute $Exe -Argument $ArgLine -WorkingDirectory $Base
$TriggerAM = New-ScheduledTaskTrigger -Daily -At ([datetime]::Today.AddHours(11))
$TriggerPM = New-ScheduledTaskTrigger -Daily -At ([datetime]::Today.AddHours(18))
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$User = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$Principal = New-ScheduledTaskPrincipal -UserId $User -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $Action `
    -Trigger @($TriggerAM, $TriggerPM) -Settings $Settings `
    -Principal $Principal -Force | Out-Null

Write-Host "已注册任务：$TaskName（每天 11:00、18:00）"
Write-Host "运行目录：$Base"
Write-Host "删除任务：.\install_task.ps1 -Unregister"
