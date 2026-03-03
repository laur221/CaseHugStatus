@echo off
:: Ruleaza ca Administrator automat
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -Command "Start-Process powershell -ArgumentList '-ExecutionPolicy Bypass -File \"%~dp0install_task_new.ps1\" install' -Verb RunAs"
pause
