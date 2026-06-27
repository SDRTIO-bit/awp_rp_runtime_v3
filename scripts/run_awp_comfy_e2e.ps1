# run_awp_comfy_e2e.ps1 — Run AWP ComfyUI E2E test suite
#
# Connects to or verifies local ComfyUI, runs comfy-api-e2e suite,
# writes local reports, returns correct exit code.
#
# Usage:
#   .\scripts\run_awp_comfy_e2e.ps1
#   .\scripts\run_awp_comfy_e2e.ps1 -ComfyUrl "http://127.0.0.1:8188"
#   .\scripts\run_awp_comfy_e2e.ps1 -Timeout 180

param(
    [string]$ComfyUrl = "http://127.0.0.1:8188",
    [int]$Timeout = 120,
    [string]$ArtifactRoot = "artifacts/test-runs"
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "AWP RP Runtime V2 — ComfyUI E2E Suite" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check Python
try {
    $pythonVersion = python --version 2>&1
    Write-Host "Python: $pythonVersion"
} catch {
    Write-Host "ERROR: Python not found in PATH" -ForegroundColor Red
    exit 2
}

# Check ComfyUI availability
Write-Host "Checking ComfyUI at $ComfyUrl ..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "$ComfyUrl/system_stats" -TimeoutSec 5 -ErrorAction Stop
    Write-Host "ComfyUI is available (status $($response.StatusCode))" -ForegroundColor Green
} catch {
    Write-Host "ERROR: ComfyUI is not available at $ComfyUrl" -ForegroundColor Red
    Write-Host "Start ComfyUI before running this script." -ForegroundColor Red
    exit 2
}

# Run E2E suite
Write-Host ""
Write-Host "Running comfy-api-e2e suite..." -ForegroundColor Yellow

$env:PYTHONPATH = (Get-Location).Path

python -m awp_rp_runtime_v2.testing.run_workflow_scenarios `
    --suite comfy-api-e2e `
    --comfy-url $ComfyUrl `
    --timeout $Timeout `
    --artifact-root $ArtifactRoot `
    --verbose

$exitCode = $LASTEXITCODE

Write-Host ""
if ($exitCode -eq 0) {
    Write-Host "All E2E scenarios PASSED" -ForegroundColor Green
} elseif ($exitCode -eq 1) {
    Write-Host "Some E2E scenarios FAILED" -ForegroundColor Red
} else {
    Write-Host "E2E suite encountered an error (exit code $exitCode)" -ForegroundColor Red
}

Write-Host "Artifacts: $ArtifactRoot/" -ForegroundColor Cyan
exit $exitCode
