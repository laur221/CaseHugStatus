# 🔧 Setup Script for CasehugAuto

Write-Host "🎰 CasehugAuto - Setup Script" -ForegroundColor Cyan
Write-Host "================================`n" -ForegroundColor Cyan

# Check Python
Write-Host "🔍 Checking Python..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✅ Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Python is not installed!" -ForegroundColor Red
    Write-Host "💡 Download Python from: https://www.python.org/downloads/" -ForegroundColor Yellow
    Read-Host "Press Enter to close"
    exit
}

# Install dependencies
Write-Host "`n📦 Installing dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Dependencies installed successfully!" -ForegroundColor Green
} else {
    Write-Host "❌ Error installing dependencies!" -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit
}

# Check config.json
Write-Host "`n⚙️ Checking configuration..." -ForegroundColor Yellow
if (Test-Path "config.json") {
    Write-Host "✅ config.json exists!" -ForegroundColor Green
    
    # Read and verify config
    $config = Get-Content "config.json" | ConvertFrom-Json
    
    if ($config.telegram_bot_token -eq "YOUR_BOT_TOKEN_HERE") {
        Write-Host "⚠️ Telegram bot token is not configured!" -ForegroundColor Red
        Write-Host "💡 Edit config.json and add your token from @BotFather" -ForegroundColor Yellow
    } else {
        Write-Host "✅ Telegram bot token configured!" -ForegroundColor Green
    }
    
    if ($config.telegram_chat_id -eq "YOUR_CHAT_ID_HERE") {
        Write-Host "⚠️ Telegram chat ID is not configured!" -ForegroundColor Red
        Write-Host "💡 Edit config.json and add your chat ID from @userinfobot" -ForegroundColor Yellow
    } else {
        Write-Host "✅ Telegram chat ID configured!" -ForegroundColor Green
    }
    
} else {
    Write-Host "❌ config.json does not exist!" -ForegroundColor Red
    Write-Host "💡 Copy config.example.json to config.json and edit it" -ForegroundColor Yellow
    
    $createConfig = Read-Host "`nDo you want to create config.json now? (Y/N)"
    if ($createConfig -eq "Y" -or $createConfig -eq "y") {
        Copy-Item "config.example.json" "config.json"
        Write-Host "✅ config.json created! Now edit it with your data." -ForegroundColor Green
    }
}

# Check Chrome
Write-Host "`n🌐 Checking Google Chrome..." -ForegroundColor Yellow
$chromePaths = @(
    "C:\Program Files\Google\Chrome\Application\chrome.exe",
    "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
)

$chromeFound = $false
foreach ($path in $chromePaths) {
    if (Test-Path $path) {
        Write-Host "✅ Chrome found at: $path" -ForegroundColor Green
        $chromeFound = $true
        break
    }
}

if (-not $chromeFound) {
    Write-Host "⚠️ Chrome not found!" -ForegroundColor Red
    Write-Host "💡 Download Chrome from: https://www.google.com/chrome/" -ForegroundColor Yellow
}

# Create profiles directory
Write-Host "`n📁 Creating profiles directory..." -ForegroundColor Yellow
if (-not (Test-Path "profiles")) {
    New-Item -ItemType Directory -Path "profiles" | Out-Null
    Write-Host "✅ Profiles directory created!" -ForegroundColor Green
} else {
    Write-Host "✅ Profiles directory exists!" -ForegroundColor Green
}

# Final summary
Write-Host "`n================================" -ForegroundColor Cyan
Write-Host "📋 SETUP SUMMARY" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

if ($chromeFound) {
    Write-Host "✅ Chrome installed" -ForegroundColor Green
} else {
    Write-Host "❌ Chrome missing" -ForegroundColor Red
}

Write-Host "✅ Python dependencies installed" -ForegroundColor Green

if (Test-Path "config.json") {
    Write-Host "✅ config.json exists" -ForegroundColor Green
} else {
    Write-Host "❌ config.json missing" -ForegroundColor Red
}

Write-Host "`n================================" -ForegroundColor Cyan
Write-Host "📚 NEXT STEPS:" -ForegroundColor Yellow
Write-Host "================================" -ForegroundColor Cyan
Write-Host "1. Edit config.json with Telegram token and chat ID" -ForegroundColor White
Write-Host "2. Configure the 4 accounts in config.json" -ForegroundColor White
Write-Host "3. Run: python main.py" -ForegroundColor White
Write-Host "4. On first run, manually login to Steam in each browser" -ForegroundColor White
Write-Host ""
Write-Host "💡 Read README.md for more details!" -ForegroundColor Yellow
Write-Host ""

Read-Host "Press Enter to close"
