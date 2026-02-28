# 🔧 Setup Script pentru CasehugAuto

Write-Host "🎰 CasehugAuto - Setup Script" -ForegroundColor Cyan
Write-Host "================================`n" -ForegroundColor Cyan

# Verifică Python
Write-Host "🔍 Verificăm Python..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✅ Python găsit: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Python nu este instalat!" -ForegroundColor Red
    Write-Host "💡 Descarcă Python de la: https://www.python.org/downloads/" -ForegroundColor Yellow
    Read-Host "Apasă Enter pentru a închide"
    exit
}

# Instalează dependențele
Write-Host "`n📦 Instalăm dependențele..." -ForegroundColor Yellow
pip install -r requirements.txt

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Dependențe instalate cu succes!" -ForegroundColor Green
} else {
    Write-Host "❌ Eroare la instalarea dependențelor!" -ForegroundColor Red
    Read-Host "Apasă Enter pentru a închide"
    exit
}

# Verifică config.json
Write-Host "`n⚙️ Verificăm configurația..." -ForegroundColor Yellow
if (Test-Path "config.json") {
    Write-Host "✅ config.json există!" -ForegroundColor Green
    
    # Citește și verifică config
    $config = Get-Content "config.json" | ConvertFrom-Json
    
    if ($config.telegram_bot_token -eq "YOUR_BOT_TOKEN_HERE") {
        Write-Host "⚠️ Telegram bot token nu este configurat!" -ForegroundColor Red
        Write-Host "💡 Editează config.json și adaugă tokenul tău de la @BotFather" -ForegroundColor Yellow
    } else {
        Write-Host "✅ Telegram bot token configurat!" -ForegroundColor Green
    }
    
    if ($config.telegram_chat_id -eq "YOUR_CHAT_ID_HERE") {
        Write-Host "⚠️ Telegram chat ID nu este configurat!" -ForegroundColor Red
        Write-Host "💡 Editează config.json și adaugă chat ID-ul tău de la @userinfobot" -ForegroundColor Yellow
    } else {
        Write-Host "✅ Telegram chat ID configurat!" -ForegroundColor Green
    }
    
} else {
    Write-Host "❌ config.json nu există!" -ForegroundColor Red
    Write-Host "💡 Copiază config.example.json la config.json și editează-l" -ForegroundColor Yellow
    
    $createConfig = Read-Host "`nVrei să creez config.json acum? (Y/N)"
    if ($createConfig -eq "Y" -or $createConfig -eq "y") {
        Copy-Item "config.example.json" "config.json"
        Write-Host "✅ config.json creat! Acum editează-l cu datele tale." -ForegroundColor Green
    }
}

# Verifică Chrome
Write-Host "`n🌐 Verificăm Google Chrome..." -ForegroundColor Yellow
$chromePaths = @(
    "C:\Program Files\Google\Chrome\Application\chrome.exe",
    "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
)

$chromeFound = $false
foreach ($path in $chromePaths) {
    if (Test-Path $path) {
        Write-Host "✅ Chrome găsit la: $path" -ForegroundColor Green
        $chromeFound = $true
        break
    }
}

if (-not $chromeFound) {
    Write-Host "⚠️ Chrome nu a fost găsit!" -ForegroundColor Red
    Write-Host "💡 Descarcă Chrome de la: https://www.google.com/chrome/" -ForegroundColor Yellow
}

# Creează directorul pentru profile
Write-Host "`n📁 Creăm directorul pentru profile..." -ForegroundColor Yellow
if (-not (Test-Path "profiles")) {
    New-Item -ItemType Directory -Path "profiles" | Out-Null
    Write-Host "✅ Director profiles creat!" -ForegroundColor Green
} else {
    Write-Host "✅ Director profiles există!" -ForegroundColor Green
}

# Sumar final
Write-Host "`n================================" -ForegroundColor Cyan
Write-Host "📋 SUMAR SETUP" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

if ($chromeFound) {
    Write-Host "✅ Chrome instalat" -ForegroundColor Green
} else {
    Write-Host "❌ Chrome lipsă" -ForegroundColor Red
}

Write-Host "✅ Dependențe Python instalate" -ForegroundColor Green

if (Test-Path "config.json") {
    Write-Host "✅ config.json există" -ForegroundColor Green
} else {
    Write-Host "❌ config.json lipsă" -ForegroundColor Red
}

Write-Host "`n================================" -ForegroundColor Cyan
Write-Host "📚 PAȘI URMĂTORI:" -ForegroundColor Yellow
Write-Host "================================" -ForegroundColor Cyan
Write-Host "1. Editează config.json cu tokenul Telegram și chat ID" -ForegroundColor White
Write-Host "2. Configurează cele 4 conturi în config.json" -ForegroundColor White
Write-Host "3. Rulează: python main.py" -ForegroundColor White
Write-Host "4. La prima rulare, loghează-te manual pe Steam în fiecare browser" -ForegroundColor White
Write-Host ""
Write-Host "💡 Citește README.md pentru mai multe detalii!" -ForegroundColor Yellow
Write-Host ""

Read-Host "Apasă Enter pentru a închide"
