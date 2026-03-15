@echo off
:: Reinstall task with multiple instance protection
cd /d "%~dp0"

echo ===================================================
echo STOPPING ALL PYTHON AND CHROME PROCESSES
echo ===================================================
taskkill /F /IM python.exe 2>nul
taskkill /F /IM pythonw.exe 2>nul
taskkill /F /IM chrome.exe 2>nul
timeout /t 2 >nul

powershell -ExecutionPolicy Bypass -Command "Start-Process powershell -ArgumentList '-ExecutionPolicy Bypass -File \"%~dp0install_task_new.ps1\" uninstall' -Verb RunAs -Wait"
timeout /t 2 >nul
powershell -ExecutionPolicy Bypass -Command "Start-Process powershell -ArgumentList '-ExecutionPolicy Bypass -File \"%~dp0install_task_new.ps1\" install' -Verb RunAs -Wait"

echo.
echo ===================================================
echo COMPLETE REINSTALL!
echo ===================================================
echo Active protections:
echo  [+] Lock file in Python (prevents multiple runs)
echo  [+] Task Scheduler: IgnoreNew (won't start if already running)
echo  [+] Browsers automatically minimized
echo ===================================================
pause
