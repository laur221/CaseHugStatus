@echo off
:: Reinstaleaza task-ul FARA CONSOLA
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -Command "Start-Process powershell -ArgumentList '-ExecutionPolicy Bypass -File \"%~dp0install_task_new.ps1\" uninstall' -Verb RunAs -Wait"
timeout /t 2 >nul
powershell -ExecutionPolicy Bypass -Command "Start-Process powershell -ArgumentList '-ExecutionPolicy Bypass -File \"%~dp0install_task_new.ps1\" install' -Verb RunAs -Wait"
echo.
echo ===================================================
echo Task reinstalat cu succes - FARA CONSOLA!
echo ===================================================
pause
