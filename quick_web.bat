@echo off
setlocal
cd /d "%~dp0"

echo Opening novel project list...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'scripts\\awp_server\.py' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
ping 127.0.0.1 -n 2 >nul
python scripts\awp_web_launcher.py --projects
if errorlevel 1 (
  echo.
  echo Launcher failed. Check the message above.
  pause
  exit /b 1
)

endlocal
