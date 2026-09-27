$ErrorActionPreference = "Stop"

$Root = "C:\Users\Admin\IMD-Nowcast\IMD-Nowcast-Bulletin-System"
$Python = Join-Path $Root "venv\Scripts\python.exe"
$Pythonw = Join-Path $Root "venv\Scripts\pythonw.exe"
$Generator = Join-Path $Root "generate_bulletin.py"
$Runner = Join-Path $Root "run_imd_scheduled.py"
$ParentVenv = "C:\Users\Admin\IMD-Nowcast\venv"
$TaskName = "IMD Nowcast Bulletin - 3 Hourly"
$CatchUpTaskName = "IMD Nowcast Bulletin - Catch Up"
$LogFile = Join-Path $Root "imd_scheduler.log"
$Times = @("00:00", "03:00", "06:00", "09:00", "12:00", "15:00", "18:00", "21:00")

if (-not (Test-Path $Generator)) {
    throw "generate_bulletin.py was not found:`n  $Generator"
}

if (-not (Test-Path $Python)) {
    if (Test-Path (Join-Path $ParentVenv "Scripts\python.exe")) {
        Write-Host "Project venv Python was not found. Linking existing IMD venv:"
        Write-Host "  $ParentVenv"
        New-Item -ItemType Junction -Path (Join-Path $Root "venv") -Target $ParentVenv | Out-Null
    }
}

if (-not (Test-Path $Python)) {
    throw "Python executable was not found:`n  $Python"
}

if (-not (Test-Path $Runner)) {
    throw "Scheduler runner was not found:`n  $Runner"
}

$taskPython = $Pythonw
if (-not (Test-Path $taskPython)) {
    $taskPython = $Python
}

Write-Host "Verified Python: $Python"
Write-Host "Verified generator: $Generator"
Write-Host "Task launcher: $taskPython $Runner"

# pythonw avoids a console window. Task Scheduler was killing cmd.exe
# with 0xC000013A (CTRL+C) before generate_bulletin.py could finish.
$action = New-ScheduledTaskAction -Execute $taskPython -Argument "`"$Runner`"" -WorkingDirectory $Root

$triggers = foreach ($time in $Times) {
    New-ScheduledTaskTrigger -Daily -At $time
}

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -WakeToRun `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 5) `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -MultipleInstances IgnoreNew
$settings.StartWhenAvailable = $false

$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $triggers `
    -Settings $settings `
    -Principal $principal `
    -Description "Runs generate_bulletin.py every 3 hours (00/03/06/09/12/15/18/21 local IST clock) without keeping VS Code open." `
    -Force | Out-Null

$catchUpAction = New-ScheduledTaskAction -Execute $taskPython -Argument "`"$Runner`" --catch-up" -WorkingDirectory $Root
$logonTrigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$catchUpTriggers = @($logonTrigger)
try {
    $startupTrigger = New-ScheduledTaskTrigger -AtStartup
    $startupTrigger.Delay = "PT1M"
    $catchUpTriggers += $startupTrigger
} catch {
    Write-Host "WARNING: could not add AtStartup catch-up trigger."
}
try {
    $eventClass = Get-CimClass -Namespace "Root/Microsoft/Windows/TaskScheduler" -ClassName "MSFT_TaskEventTrigger"
    $wakeTrigger = $eventClass | New-CimInstance -ClientOnly
    $wakeTrigger.Enabled = $true
    $wakeTrigger.Subscription = '<QueryList><Query Id="0" Path="System"><Select Path="System">*[System[Provider[@Name="Microsoft-Windows-Kernel-Power"] and (EventID=107)]]</Select></Query></QueryList>'
    $catchUpTriggers += $wakeTrigger
    Write-Host "Added resume-from-sleep catch-up trigger."
} catch {
    Write-Host "WARNING: could not add resume-from-sleep trigger. Logon catch-up is still registered."
}

$catchUpSettings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -WakeToRun `
    -RestartCount 2 `
    -RestartInterval (New-TimeSpan -Minutes 2) `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
    -MultipleInstances IgnoreNew

try {
    Register-ScheduledTask `
        -TaskName $CatchUpTaskName `
        -Action $catchUpAction `
        -Trigger $catchUpTriggers `
        -Settings $catchUpSettings `
        -Principal $principal `
        -Description "On startup/logon/resume, generate only missed IST 3-hour bulletin slots. Never generates a future slot." `
        -Force | Out-Null
} catch {
    Write-Host "Startup/wake catch-up needs elevation. Registering logon-only catch-up instead."
    Register-ScheduledTask `
        -TaskName $CatchUpTaskName `
        -Action $catchUpAction `
        -Trigger $logonTrigger `
        -Settings $catchUpSettings `
        -Principal $principal `
        -Description "On logon, generate only missed IST 3-hour bulletin slots. Never generates a future slot." `
        -Force | Out-Null
}

Write-Host ""
Write-Host "Registered scheduled task: $TaskName"
Write-Host "Registered catch-up task: $CatchUpTaskName"
Write-Host "Python executable: $taskPython"
Write-Host "Working directory: $Root"
Write-Host "Trigger schedule (local/IST clock): $($Times -join ', ')"
Write-Host "Log file: $LogFile"
Write-Host ""
Write-Host "Manually run/test the scheduled task:"
Write-Host "  schtasks /Run /TN `"$TaskName`""
Write-Host "Manually run/test catch-up only:"
Write-Host "  schtasks /Run /TN `"$CatchUpTaskName`""
Write-Host "Simulate catch-up decisions (no bulletin generation):"
Write-Host "  `"$Python`" `"$Runner`" --simulate"
Write-Host "Check task status:"
Write-Host "  schtasks /Query /TN `"$TaskName`" /V /FO LIST"
Write-Host ""
Write-Host "The tasks were registered only. generate_bulletin.py was not started by this setup script."
