# Run once to schedule the sync every day at 20:30.
$ErrorActionPreference = "Stop"

$TaskName = "Paper Monitor Git Sync 20_30"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BatPath = Join-Path $ScriptDir "sync_github_then_push_paper_monitor.bat"

if (-not (Test-Path -LiteralPath $BatPath)) {
    throw "BAT file not found: $BatPath"
}

$Argument = '/c ""' + $BatPath + '""'

$Action = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument $Argument `
    -WorkingDirectory $ScriptDir

$Trigger = New-ScheduledTaskTrigger -Daily -At "20:30"

$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Pull GitHub repository root successfully, then push Paper Monitor changes." `
    -Force | Out-Null

Write-Host ""
Write-Host "Scheduled task created successfully."
Write-Host "Task name : $TaskName"
Write-Host "Run time  : Every day at 20:30"
Write-Host "BAT file  : $BatPath"
Write-Host ""
Write-Host "The BAT blocks push whenever the preceding pull/rebase fails."
