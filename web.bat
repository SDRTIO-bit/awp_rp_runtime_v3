@echo off
setlocal
cd /d "%~dp0"
python scripts\awp_web_launcher.py %*
endlocal
