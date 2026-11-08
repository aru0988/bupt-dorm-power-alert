@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath 'py' -ArgumentList '-3.10','\"%~dp0refresh_cookie.py\"' -Verb RunAs -Wait"
echo.
pause
