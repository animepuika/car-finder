$ErrorActionPreference = "Stop"

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Start-Process powershell.exe -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    exit
}

$scriptDir = Split-Path -Parent $PSCommandPath
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-ExecutionPolicy Bypass -File `"$scriptDir\run_fetch.ps1`""
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 20) -RepetitionDuration (New-TimeSpan -Days 3650)
$settings = New-ScheduledTaskSettingsSet -WakeToRun -StartWhenAvailable
Register-ScheduledTask -TaskName "CarFinderFetch" -Action $action -Trigger $trigger -Settings $settings -Description "Fetch new ss.com car listings every 20 minutes, waking the PC if asleep" -Force | Out-Null

Write-Host ""
Write-Host "Done. CarFinderFetch is now scheduled to run every 20 minutes." -ForegroundColor Green
Write-Host ""
Read-Host "Press Enter to close this window"
