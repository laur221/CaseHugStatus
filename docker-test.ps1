# Script de testare rapida Docker pentru CasehugBot (Windows)

Write-Host "CasehugBot - Docker Test Script" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# Verificare Docker
Write-Host "Verificam Docker..." -ForegroundColor Yellow
try {
    $dockerVersion = docker --version 2>&1
    Write-Host "[OK] Docker: $dockerVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Docker nu este instalat sau nu ruleaza!" -ForegroundColor Red
    Write-Host "[INFO] Porneste Docker Desktop" -ForegroundColor Yellow
    Write-Host "[INFO] Sau instaleaza de la: https://www.docker.com/products/docker-desktop" -ForegroundColor Yellow
    Read-Host "Apasa Enter pentru a inchide"
    exit 1
}

try {
    $composeVersion = docker-compose --version 2>&1
    Write-Host "[OK] Docker Compose: $composeVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Docker Compose nu este disponibil!" -ForegroundColor Red
    Read-Host "Apasa Enter pentru a inchide"
    exit 1
}

Write-Host ""

# Verificare config.json
Write-Host "Verificam config.json..." -ForegroundColor Yellow
if (-not (Test-Path "config.json")) {
    Write-Host "[WARN] config.json nu exista!" -ForegroundColor Red
    
    if (Test-Path "config.example.json") {
        Write-Host "[INFO] Creez din config.example.json..." -ForegroundColor Yellow
        Copy-Item "config.example.json" "config.json"
        Write-Host "[OK] config.json creat!" -ForegroundColor Green
        Write-Host "[IMPORTANT] Editeaza config.json cu datele tale!" -ForegroundColor Red
        Write-Host ""
        
        # Deschide config.json in editor
        $openConfig = Read-Host "Vrei sa deschid config.json in editor? (Y/N)"
        if ($openConfig -eq "Y" -or $openConfig -eq "y") {
            notepad config.json
        }
        
        Write-Host ""
        Read-Host "Apasa Enter dupa ce ai editat config.json"
    } else {
        Write-Host "[ERROR] config.example.json lipseste!" -ForegroundColor Red
        Read-Host "Apasa Enter pentru a inchide"
        exit 1
    }
}

Write-Host "[OK] config.json exista" -ForegroundColor Green
Write-Host ""

# Verificare si creare directoare
Write-Host "Creez directoare necesare..." -ForegroundColor Yellow
if (-not (Test-Path "profiles")) {
    New-Item -ItemType Directory -Path "profiles" | Out-Null
}
if (-not (Test-Path "debug_output")) {
    New-Item -ItemType Directory -Path "debug_output" | Out-Null
}
Write-Host "[OK] Directoare create" -ForegroundColor Green
Write-Host ""

# Build imagine Docker
Write-Host "Build imagine Docker..." -ForegroundColor Yellow
Write-Host "Poate dura 2-5 minute prima data..." -ForegroundColor Yellow
Write-Host ""

docker-compose build

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "[OK] Imagine construita cu succes!" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "[ERROR] Eroare la build imagine!" -ForegroundColor Red
    Read-Host "Apasa Enter pentru a inchide"
    exit 1
}

Write-Host ""
Write-Host "==================================" -ForegroundColor Cyan
Write-Host "Rulare bot in Docker..." -ForegroundColor Cyan
Write-Host "==================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "[INFO] Pentru a opri: Ctrl+C" -ForegroundColor Yellow
Write-Host "[INFO] Pentru logs: docker-compose logs -f" -ForegroundColor Yellow
Write-Host "[INFO] Pentru debug: verifica .\debug_output\" -ForegroundColor Yellow
Write-Host ""

# Intreaba daca vrea sa ruleze in background
$runMode = Read-Host "Vrei sa rulezi in background? (Y/N) [N]"
Write-Host ""

if ($runMode -eq "Y" -or $runMode -eq "y") {
    # Ruleaza in background
    docker-compose up -d
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] Bot pornit in background!" -ForegroundColor Green
        Write-Host ""
        Write-Host "Comenzi utile:" -ForegroundColor Yellow
        Write-Host "   docker-compose logs -f" -ForegroundColor White
        Write-Host "   (Vezi logs live)" -ForegroundColor Gray
        Write-Host ""
        Write-Host "   docker-compose ps" -ForegroundColor White
        Write-Host "   (Status container)" -ForegroundColor Gray
        Write-Host ""
        Write-Host "   docker-compose down" -ForegroundColor White
        Write-Host "   (Opreste bot)" -ForegroundColor Gray
        Write-Host ""
        Write-Host "   docker-compose restart" -ForegroundColor White
        Write-Host "   (Reporneste bot)" -ForegroundColor Gray
    } else {
        Write-Host "[ERROR] Eroare la pornire container!" -ForegroundColor Red
    }
} else {
    # Ruleaza in foreground
    docker-compose up
    
    Write-Host ""
    Write-Host "==================================" -ForegroundColor Cyan
    Write-Host "Bot oprit" -ForegroundColor Cyan
    Write-Host "==================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Pentru a rula in background:" -ForegroundColor Yellow
    Write-Host "   docker-compose up -d" -ForegroundColor White
    Write-Host ""
    Write-Host "Pentru a vedea logs:" -ForegroundColor Yellow
    Write-Host "   docker-compose logs -f" -ForegroundColor White
    Write-Host ""
    Write-Host "Pentru debugging:" -ForegroundColor Yellow
    Write-Host "   dir debug_output" -ForegroundColor White
    Write-Host ""
}

Read-Host "Apasa Enter pentru a inchide"
