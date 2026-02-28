@echo off
chcp 65001 >nul
title CasehugAuto - Bot Automatizare
color 0A

echo.
echo ═══════════════════════════════════════════════
echo   🎰 CasehugAuto - Starting Bot...
echo ═══════════════════════════════════════════════
echo.

REM Verifică dacă config.json există
if not exist "config.json" (
    echo ❌ config.json nu există!
    echo 💡 Rulează setup.ps1 sau creează config.json manual
    echo.
    pause
    exit /b 1
)

REM Verifică dacă Python există
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python nu este instalat!
    echo 💡 Descarcă Python de la https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

echo ✅ Configurație găsită
echo ✅ Python instalat
echo.
echo 🚀 Pornire bot...
echo.

REM Rulează botul
python main.py

echo.
echo ═══════════════════════════════════════════════
echo   Botul s-a oprit
echo ═══════════════════════════════════════════════
echo.
pause
