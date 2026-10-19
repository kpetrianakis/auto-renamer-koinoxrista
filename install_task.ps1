# Καταχωρεί τον watcher στον Task Scheduler: ξεκινά στο login, ξανασηκώνεται αν πέσει.
$ErrorActionPreference = 'Stop'
$taskName = 'Koinoxrista Auto-Renamer'
$pythonw = Join-Path $PSScriptRoot '.venv\Scripts\pythonw.exe'
if (-not (Test-Path $pythonw)) { throw "Δεν βρέθηκε το $pythonw — φτιάξε πρώτα το .venv" }

$action = New-ScheduledTaskAction -Execute $pythonw -Argument '-m renamer' -WorkingDirectory $PSScriptRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet `
    -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName $taskName
Get-ScheduledTask -TaskName $taskName | Select-Object TaskName, State
