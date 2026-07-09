@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
set "NOVEL_DIR=%~1"

if not "%NOVEL_DIR%"=="" (
    python "%SCRIPT_DIR%scripts\awp_tui.py" "%NOVEL_DIR%"
) else (
    python "%SCRIPT_DIR%scripts\awp_tui.py"
)
