@echo off
setlocal

rem Windows keeps the original direct-Python behavior. Interpreter failures
rem fail open because telemetry must never block or break a Codex turn.
if defined CODEX_LOGFIRE_PYTHON (
    "%CODEX_LOGFIRE_PYTHON%" "%~dp0codex_logfire_hook.py"
    exit /b 0
)

where python3.exe >nul 2>nul
if not errorlevel 1 (
    python3 "%~dp0codex_logfire_hook.py"
    if not errorlevel 1 exit /b 0
)

where py.exe >nul 2>nul
if not errorlevel 1 (
    py -3 "%~dp0codex_logfire_hook.py"
    if not errorlevel 1 exit /b 0
)

where python.exe >nul 2>nul
if not errorlevel 1 (
    python "%~dp0codex_logfire_hook.py"
)

exit /b 0
