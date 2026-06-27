# register_awp_comfy_e2e_task.ps1 — Register Windows scheduled task for E2E tests
#
# Creates an OPTIONAL Windows Task Scheduler job that runs the E2E suite daily.
# Default: daily at 03:17 Asia/Tokyo local time (18:17 UTC previous day).
#
# Time configuration:
#   GitHub nightly cron: 18:17 UTC = 03:17 Asia/Tokyo next day
#   Windows scheduled task: 03:17 local (Asia/Tokyo)
#   Both fire at the same absolute moment.
#
# IMPORTANT:
#   - This script does NOT auto-register. You must run it explicitly.
#   - It does NOT access real models.
#   - It does NOT commit code.
#   - It does NOT modify main.
#
# Usage:
#   .\scripts\register_awp_comfy_e2e_task.ps1
#   .\scripts\register_awp_comfy_e2e_task.ps1 -Remove

param(
    [switch]$Remove,
    [string]$TaskName = "AWP-RP-ComfyUI-E2E",
    [string]$Time = "03:17"
)

$ErrorActionPreference = "Stop"

$scriptPath = Join-Path $PSScriptRoot "run_awp_comfy_e2e.ps1"
$repoRoot = Split-Path $PSScriptRoot -Parent

if ($Remove) {
    Write-Host "Removing scheduled task '$TaskName'..." -ForegroundColor Yellow
    try {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction Stop
        Write-Host "Task '$TaskName' removed." -ForegroundColor Green
    } catch {
        Write-Host "Task '$TaskName' not found or already removed." -ForegroundColor Yellow
    }
    exit 0
}

# Verify the E2E script exists
if (-not (Test-Path $scriptPath)) {
    Write-Host "ERROR: E2E script not found at $scriptPath" -ForegroundColor Red
    exit 1
}

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Register AWP ComfyUI E2E Scheduled Task" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Task Name: $TaskName" -ForegroundColor White
Write-Host "Schedule:  Daily at $Time (Asia/Tokyo local)" -ForegroundColor White
Write-Host "Script:    $scriptPath" -ForegroundColor White
Write-Host "Work Dir:  $repoRoot" -ForegroundColor White
Write-Host ""

# Create the action
$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`"" `
    -WorkingDirectory $repoRoot

# Create the trigger (daily at specified time)
$trigger = New-ScheduledTaskTrigger -Daily -At $Time

# Create the settings
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable

# Register the task
Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "AWP RP Runtime V2 - ComfyUI E2E test suite (daily)" `
    -RunLevel Limited

Write-Host ""
Write-Host "Task '$TaskName' registered successfully." -ForegroundColor Green
Write-Host "To run manually:  schtasks /run /tn `"$TaskName`"" -ForegroundColor Cyan
Write-Host "To remove:        .\scripts\register_awp_comfy_e2e_task.ps1 -Remove" -ForegroundColor Cyan
