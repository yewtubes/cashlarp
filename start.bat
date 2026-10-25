@echo off
cd /d "%~dp0"
echo Open http://127.0.0.1:3000/login
where py >nul 2>nul
if errorlevel 1 (
  python -B run.py %*
) else (
  py -3 -B run.py %*
)
pause
