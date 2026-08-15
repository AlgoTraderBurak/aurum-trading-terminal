@echo off
setlocal
title AURUM Piyasa Analiz Terminali
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Sanal ortam bulunamadi. Once KURULUM.bat dosyasini calistirin.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m app.main
if errorlevel 1 pause
endlocal
