$ErrorActionPreference = "Stop"

$TaskNames = @(
    "IMD Nowcast Bulletin - 3 Hourly",
    "IMD Nowcast Bulletin - Catch Up"
)

foreach ($TaskName in $TaskNames) {
    $existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if (-not $existing) {
        Write-Host "Scheduled task not found: $TaskName"
        continue
    }
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed scheduled task: $TaskName"
}
