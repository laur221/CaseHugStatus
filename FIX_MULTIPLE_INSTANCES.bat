@echo off
:: Reinstaleaza task-ul cu protectie contra instante multiple
cd /d "%~dp0"

echo ===================================================
echo OPRESC TOATE PROCESELE PYTHON SI CHROME
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
echo REINSTALARE COMPLETA!
echo ===================================================
echo Protectii active:
echo  [+] Lock file in Python (previne rulari multiple)
echo  [+] Task Scheduler: IgnoreNew (nu porneste daca ruleaza)
echo  [+] Browsere minimizate automat
echo ===================================================
pause
