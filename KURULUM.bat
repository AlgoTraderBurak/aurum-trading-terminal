@echo off
setlocal
title AURUM Kurulum
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" python -m venv .venv
".venv\Scripts\python.exe" -m pip install --upgrade pip
if exist "requirements.lock" (
    ".venv\Scripts\python.exe" -m pip install -r requirements.lock
) else (
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)
echo.
echo Kurulum tamamlandi. AURUM.bat ile uygulamayi acabilirsiniz.
pause
endlocal
