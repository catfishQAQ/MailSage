@echo off
setlocal
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"

if exist "backend\.venv\Scripts\python.exe" (
  "backend\.venv\Scripts\python.exe" "scripts\stop_mailsage.py"
) else (
  where py >nul 2>nul
  if %errorlevel%==0 (
    py "scripts\stop_mailsage.py"
  ) else (
    python "scripts\stop_mailsage.py"
  )
)

if errorlevel 1 (
  echo.
  echo MailSage stop failed. Press any key to close this window.
  pause >nul
)

endlocal
