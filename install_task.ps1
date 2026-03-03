# CasehugBot Task Scheduler - Instalare Automată
# Rulează ca Administrator: Right-click → Run as Administrator

param(
    [string]$Action = "install"  # install, uninstall, start, stop, status
)

$taskName = "CasehugBot Scheduler"
$scriptPath = Join-Path $PSScriptRoot "run_scheduler.bat"
$workingDir = $PSScriptRoot

function Show-Banner {
    Write-Host ""
    Write-Host "╔═══════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║        CASEHUGBOT SCHEDULER - TASK INSTALLER           ║" -ForegroundColor Cyan
    Write-Host "╚═══════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""
}

function Test-Administrator {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Install-Task {
    Write-Host "📋 Instalare Task Scheduler..." -ForegroundColor Yellow
    
    # Verifică dacă scriptul există
    if (-not (Test-Path $scriptPath)) {
        Write-Host "❌ Eroare: $scriptPath nu există!" -ForegroundColor Red
        return $false
    }
    
    # Șterge task existent dacă există
    $existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($existingTask) {
        Write-Host "   🗑️  Șterge task existent..." -ForegroundColor Yellow
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    }
    
    try {
        # Creează acțiunea
        $action = New-ScheduledTaskAction -Execute $scriptPath -WorkingDirectory $workingDir
        
        # Creează trigger (la pornirea sistemului + repetare la 5 minute)
        $trigger = New-ScheduledTaskTrigger -AtStartup
        $trigger.Repetition = (New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 5)).Repetition
        
        # Setări avansate
        $settings = New-ScheduledTaskSettingsSet `
            -AllowStartIfOnBatteries `
            -DontStopIfGoingOnBatteries `
            -StartWhenAvailable `
            -DontStopOnIdleEnd `
            -ExecutionTimeLimit (New-TimeSpan -Hours 0)  # Fără limită de timp
        
        # Principal (utilizator curent, cele mai mari privilegii)
        $principal = New-ScheduledTaskPrincipal `
            -UserId $env:USERNAME `
            -LogonType Interactive `
            -RunLevel Highest
        
        # Înregistrează task-ul
        Register-ScheduledTask `
            -TaskName $taskName `
            -Action $action `
            -Trigger $trigger `
            -Settings $settings `
            -Principal $principal `
            -Description "Rulare automată CasehugBot cu tracking individual per cont (verificare la 5 minute)" `
            -Force | Out-Null
        
        Write-Host "✅ Task Scheduler instalat cu succes!" -ForegroundColor Green
        Write-Host ""
        Write-Host "📋 Detalii task:" -ForegroundColor Cyan
        Write-Host "   Nume: $taskName"
        Write-Host "   Trigger: La pornirea sistemului + repetare la fiecare 5 minute"
        Write-Host "   Script: $scriptPath"
        Write-Host "   Working Dir: $workingDir"
        Write-Host "   Sistem: Tracking individual per cont (24h de la ultima deschidere)"
        Write-Host ""
        
        return $true
    }
    catch {
        Write-Host "❌ Eroare instalare: $_" -ForegroundColor Red
        return $false
    }
}

function Uninstall-Task {
    Write-Host "🗑️  Dezinstalare Task Scheduler..." -ForegroundColor Yellow
    
    $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($task) {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
        Write-Host "✅ Task șters cu succes!" -ForegroundColor Green
    }
    else {
        Write-Host "⚠️  Task-ul nu există" -ForegroundColor Yellow
    }
}

function Start-Task {
    Write-Host "▶️  Pornire task..." -ForegroundColor Yellow
    
    $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($task) {
        Start-ScheduledTask -TaskName $taskName
        Write-Host "✅ Task pornit!" -ForegroundColor Green
        Start-Sleep -Seconds 2
        Show-Status
    }
    else {
        Write-Host "❌ Task-ul nu există! Rulează: .\install_task.ps1 install" -ForegroundColor Red
    }
}

function Stop-Task {
    Write-Host "⏹️  Oprire task..." -ForegroundColor Yellow
    
    $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($task) {
        Stop-ScheduledTask -TaskName $taskName
        Write-Host "✅ Task oprit!" -ForegroundColor Green
    }
    else {
        Write-Host "❌ Task-ul nu există!" -ForegroundColor Red
    }
}

function Show-Status {
    $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    
    if ($task) {
        $info = Get-ScheduledTaskInfo -TaskName $taskName
        
        Write-Host ""
        Write-Host "📊 STATUS TASK SCHEDULER" -ForegroundColor Cyan
        Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
        Write-Host "Nume task:         " -NoNewline; Write-Host $task.TaskName -ForegroundColor White
        Write-Host "Status:            " -NoNewline
        
        if ($task.State -eq "Running") {
            Write-Host "🟢 Rulează" -ForegroundColor Green
        }
        elseif ($task.State -eq "Ready") {
            Write-Host "🟡 Gata (Așteaptă trigger)" -ForegroundColor Yellow
        }
        else {
            Write-Host "🔴 $($task.State)" -ForegroundColor Red
        }
        
        Write-Host "Ultima rulare:     " -NoNewline; Write-Host $info.LastRunTime -ForegroundColor White
        Write-Host "Următoarea rulare:" -NoNewline; Write-Host $info.NextRunTime -ForegroundColor White
        Write-Host "Ultimul rezultat:  " -NoNewline
        
        if ($info.LastTaskResult -eq 0) {
            Write-Host "✅ Success (0)" -ForegroundColor Green
        }
        else {
            Write-Host "❌ Eroare ($($info.LastTaskResult))" -ForegroundColor Red
        }
        
        Write-Host ""
        
        # Verifică last_run.txt
        $lastRunFile = Join-Path $PSScriptRoot "last_run.txt"
        if (Test-Path $lastRunFile) {
            $lastRunContent = Get-Content $lastRunFile -Raw
            Write-Host "📅 Ultima rulare bot: " -NoNewline
            Write-Host $lastRunContent -ForegroundColor Yellow
        }
        
        Write-Host ""
    }
    else {
        Write-Host ""
        Write-Host "⚠️  Task-ul nu este instalat" -ForegroundColor Yellow
        Write-Host "   Rulează: .\install_task.ps1 install" -ForegroundColor Cyan
        Write-Host ""
    }
}

function Show-Help {
    Write-Host "UTILIZARE:" -ForegroundColor Cyan
    Write-Host "  .\install_task.ps1 [install|uninstall|start|stop|status]"
    Write-Host ""
    Write-Host "COMENZI:" -ForegroundColor Cyan
    Write-Host "  install   - Instalează task în Task Scheduler"
    Write-Host "  uninstall - Șterge task din Task Scheduler"
    Write-Host "  start     - Pornește task-ul manual"
    Write-Host "  stop      - Oprește task-ul"
    Write-Host "  status    - Afișează status task (default)"
    Write-Host ""
    Write-Host "EXEMPLE:" -ForegroundColor Cyan
    Write-Host "  .\install_task.ps1 install"
    Write-Host "  .\install_task.ps1 status"
    Write-Host ""
}

# ══════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════

Show-Banner

# Verifică privilegii Administrator
if (-not (Test-Administrator)) {
    Write-Host "❌ EROARE: Acest script necesită privilegii de Administrator!" -ForegroundColor Red
    Write-Host ""
    Write-Host "💡 Soluție:" -ForegroundColor Yellow
    Write-Host "   1. Închide fereastra PowerShell"
    Write-Host "   2. Click dreapta pe PowerShell"
    Write-Host "   3. Selectează 'Run as Administrator'"
    Write-Host "   4. Rulează din nou: .\install_task.ps1 install"
    Write-Host ""
    exit 1
}

switch ($Action.ToLower()) {
    "install" {
        if (Install-Task) {
            Write-Host "🎉 Instalare completată!" -ForegroundColor Green
            Write-Host ""
            Write-Host "NEXT STEPS:" -ForegroundColor Cyan
            Write-Host "  1. Editează 'schedule_config.json' cu ora dorită"
            Write-Host "  2. Adaugă Steam la conturile dorite în 'config.json'"
            Write-Host "  3. Task-ul va porni automat la următorul restart"
            Write-Host "  4. Sau pornește manual: .\install_task.ps1 start"
            Write-Host ""
        }
    }
    "uninstall" {
        Uninstall-Task
    }
    "start" {
        Start-Task
    }
    "stop" {
        Stop-Task
    }
    "status" {
        Show-Status
    }
    "help" {
        Show-Help
    }
    default {
        Show-Status
    }
}
