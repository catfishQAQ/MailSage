@echo off
setlocal
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"

if exist "backend\.venv\Scripts\python.exe" (
  "backend\.venv\Scripts\python.exe" "scripts\start_mailsage.py"
) else (
  where py >nul 2>nul
  if %errorlevel%==0 (
    py "scripts\start_mailsage.py"
  ) else (
    python "scripts\start_mailsage.py"
  )
)

if errorlevel 1 (
  echo.
  echo MailSage launcher failed. Press any key to close this window.
  pause >nul
)

endlocal
