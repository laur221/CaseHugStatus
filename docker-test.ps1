# 🐳 Script de testare rapidă Docker pentru CasehugBot (Windows)

Write-Host "🐳 CasehugBot - Docker Test Script" -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""

# Verificare Docker
Write-Host "🔍 Verificăm Docker..." -ForegroundColor Yellow
try {
    $dockerVersion = docker --version 2>&1
    Write-Host "✅ Docker: $dockerVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker nu este instalat sau nu rulează!" -ForegroundColor Red
    Write-Host "💡 Pornește Docker Desktop" -ForegroundColor Yellow
    Write-Host "💡 Sau instalează de la: https://www.docker.com/products/docker-desktop" -ForegroundColor Yellow
    Read-Host "Apasă Enter pentru a închide"
    exit 1
}

try {
    $composeVersion = docker-compose --version 2>&1
    Write-Host "✅ Docker Compose: $composeVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Docker Compose nu este disponibil!" -ForegroundColor Red
    Read-Host "Apasă Enter pentru a închide"
    exit 1
}

Write-Host ""

# Verificare config.json
Write-Host "📝 Verificăm config.json..." -ForegroundColor Yellow
if (-not (Test-Path "config.json")) {
    Write-Host "⚠️ config.json nu există!" -ForegroundColor Red
    
    if (Test-Path "config.example.json") {
        Write-Host "💡 Creez din config.example.json..." -ForegroundColor Yellow
        Copy-Item "config.example.json" "config.json"
        Write-Host "✅ config.json creat!" -ForegroundColor Green
        Write-Host "⚠️ IMPORTANT: Editează config.json cu datele tale!" -ForegroundColor Red
        Write-Host ""
        
        # Deschide config.json în editor
        $openConfig = Read-Host "Vrei să deschid config.json în editor? (Y/N)"
        if ($openConfig -eq "Y" -or $openConfig -eq "y") {
            notepad config.json
        }
        
        Write-Host ""
        Read-Host "Apasă Enter după ce ai editat config.json"
    } else {
        Write-Host "❌ config.example.json lipsește!" -ForegroundColor Red
        Read-Host "Apasă Enter pentru a închide"
        exit 1
    }
}

Write-Host "✅ config.json există" -ForegroundColor Green
Write-Host ""

# Verificare și creare directoare
Write-Host "📁 Creez directoare necesare..." -ForegroundColor Yellow
if (-not (Test-Path "profiles")) {
    New-Item -ItemType Directory -Path "profiles" | Out-Null
}
if (-not (Test-Path "debug_output")) {
    New-Item -ItemType Directory -Path "debug_output" | Out-Null
}
Write-Host "✅ Directoare create" -ForegroundColor Green
Write-Host ""

# Build imagine Docker
Write-Host "🔨 Build imagine Docker..." -ForegroundColor Yellow
Write-Host "⏱️ Poate dura 2-5 minute prima dată..." -ForegroundColor Yellow
Write-Host ""

docker-compose build

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✅ Imagine construită cu succes!" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "❌ Eroare la build imagine!" -ForegroundColor Red
    Read-Host "Apasă Enter pentru a închide"
    exit 1
}

Write-Host ""
Write-Host "==================================" -ForegroundColor Cyan
Write-Host "🚀 Rulare bot în Docker..." -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "💡 Pentru a opri: Ctrl+C" -ForegroundColor Yellow
Write-Host "💡 Pentru logs: docker-compose logs -f" -ForegroundColor Yellow
Write-Host "💡 Pentru debug: verifică .\debug_output\" -ForegroundColor Yellow
Write-Host ""

# Întreabă dacă vrea să ruleze în background
$runMode = Read-Host "Vrei să rulezi în background? (Y/N) [N]"
Write-Host ""

if ($runMode -eq "Y" -or $runMode -eq "y") {
    # Rulează în background
    docker-compose up -d
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Bot pornit în background!" -ForegroundColor Green
        Write-Host ""
        Write-Host "📊 Comenzi utile:" -ForegroundColor Yellow
        Write-Host "   docker-compose logs -f" -ForegroundColor White
        Write-Host "   (Vezi logs live)" -ForegroundColor Gray
        Write-Host ""
        Write-Host "   docker-compose ps" -ForegroundColor White
        Write-Host "   (Status container)" -ForegroundColor Gray
        Write-Host ""
        Write-Host "   docker-compose down" -ForegroundColor White
        Write-Host "   (Oprește bot)" -ForegroundColor Gray
        Write-Host ""
        Write-Host "   docker-compose restart" -ForegroundColor White
        Write-Host "   (Repornește bot)" -ForegroundColor Gray
    } else {
        Write-Host "❌ Eroare la pornire container!" -ForegroundColor Red
    }
} else {
    # Rulează în foreground
    docker-compose up
    
    Write-Host ""
    Write-Host "==================================" -ForegroundColor Cyan
    Write-Host "👋 Bot oprit" -ForegroundColor Cyan
    Write-Host "==================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "📊 Pentru a rula în background:" -ForegroundColor Yellow
    Write-Host "   docker-compose up -d" -ForegroundColor White
    Write-Host ""
    Write-Host "📋 Pentru a vedea logs:" -ForegroundColor Yellow
    Write-Host "   docker-compose logs -f" -ForegroundColor White
    Write-Host ""
    Write-Host "🐛 Pentru debugging:" -ForegroundColor Yellow
    Write-Host "   dir debug_output" -ForegroundColor White
    Write-Host ""
}

Read-Host "Apasă Enter pentru a închide"
