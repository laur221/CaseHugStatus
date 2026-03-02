@echo off
REM CasehugBot Scheduler - Rulare automată în background

cd /d "%~dp0"

REM Activează virtual environment dacă există
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

REM Rulează scheduler-ul în mod minimized
pythonw scheduler.py

REM pythonw = Python fără consolă (complet ascuns)
REM Pentru debugging cu consolă, înlocuiește cu: python scheduler.py
