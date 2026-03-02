# 🚀 CasehugBot Scheduler - Quick Start

Write-Host ""
Write-Host "╔═══════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║         CASEHUGBOT SCHEDULER - QUICK START             ║" -ForegroundColor Cyan
Write-Host "╚═══════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

Write-Host "PASUL 1: Instalare dependențe" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""

# Activează venv dacă există
if (Test-Path ".venv\Scripts\Activate.ps1") {
    Write-Host "   🐍 Activare virtual environment..." -ForegroundColor Cyan
    & .\.venv\Scripts\Activate.ps1
}

Write-Host "   📦 Instalare psutil (pentru detectare Steam)..." -ForegroundColor Cyan
pip install psutil==5.9.8 --quiet
Write-Host "   ✅ Dependențe instalate!" -ForegroundColor Green
Write-Host ""

Write-Host "PASUL 2: Configurare" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""

$configFile = "schedule_config.json"

if (Test-Path $configFile) {
    Write-Host "   ✅ $configFile există" -ForegroundColor Green
    $config = Get-Content $configFile -Raw | ConvertFrom-Json
    Write-Host "   ⏰ Oră programată: $($config.run_time)" -ForegroundColor Cyan
    Write-Host "   🎮 Verificare Steam: $($config.require_steam_login)" -ForegroundColor Cyan
    Write-Host "   📦 Conturi Steam: $($config.accounts_with_steam -join ', ')" -ForegroundColor Cyan
}
else {
    Write-Host "   ⚠️  $configFile lipsește - se va crea la prima rulare" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "   💡 Pentru a edita configurația:" -ForegroundColor Yellow
Write-Host "      notepad $configFile" -ForegroundColor White
Write-Host ""

Write-Host "PASUL 3: Test Scheduler (Manual)" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
Write-Host ""
Write-Host "   Vrei să testezi scheduler-ul acum? (y/n): " -ForegroundColor Cyan -NoNewline
$testNow = Read-Host

if ($testNow -eq "y" -or $testNow -eq "Y") {
    Write-Host ""
    Write-Host "   🚀 Pornesc scheduler în mod test..." -ForegroundColor Green
    Write-Host "   💡 Apasă Ctrl+C pentru a opri" -ForegroundColor Yellow
    Write-Host ""
    Start-Sleep -Seconds 2
    
    python scheduler.py
}
else {
    Write-Host ""
    Write-Host "PASUL 4: Instalare Task Scheduler (Opțional)" -ForegroundColor Yellow
    Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "   Pentru rulare automată la pornirea laptop-ului:" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "   1. Deschide PowerShell ca Administrator" -ForegroundColor White
    Write-Host "   2. Navighează în $PWD" -ForegroundColor White
    Write-Host "   3. Rulează: .\install_task.ps1 install" -ForegroundColor Green
    Write-Host ""
    Write-Host "   Sau citește ghidul complet: SETUP_SCHEDULER.md" -ForegroundColor Yellow
    Write-Host ""
}

Write-Host ""
Write-Host "╔═══════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║                    READY TO GO! 🚀                     ║" -ForegroundColor Green
Write-Host "╚═══════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "COMENZI UTILE:" -ForegroundColor Cyan
Write-Host "  python scheduler.py           - Test manual scheduler" -ForegroundColor White
Write-Host "  python main.py                - Rulare imediata bot (o data)" -ForegroundColor White
Write-Host "  .\install_task.ps1 install    - Instaleaza Task Scheduler (Admin)" -ForegroundColor White
Write-Host "  .\install_task.ps1 status     - Verifica status task" -ForegroundColor White
Write-Host ""
