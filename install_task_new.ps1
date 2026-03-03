# CasehugBot Task Scheduler - Instalare Automata
# Ruleaza ca Administrator: Right-click -> Run as Administrator

param(
    [string]$Action = "install"
)

$taskName = "CasehugBot Scheduler"
$scriptPath = Join-Path $PSScriptRoot "run_scheduler_hidden.vbs"
$workingDir = $PSScriptRoot

function Test-Administrator {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Install-Task {
    Write-Host "Instalare Task Scheduler..." -ForegroundColor Yellow
    
    if (-not (Test-Path $scriptPath)) {
        Write-Host "Eroare: $scriptPath nu exista!" -ForegroundColor Red
        return $false
    }
    
    $existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($existingTask) {
        Write-Host "Sterg task existent..." -ForegroundColor Yellow
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    }
    
    try {
        # Foloseste wscript.exe pentru a rula VBScript-ul complet ascuns
        $wscriptPath = "C:\Windows\System32\wscript.exe"
        $action = New-ScheduledTaskAction -Execute $wscriptPath -Argument "`"$scriptPath`"" -WorkingDirectory $workingDir
        
        $trigger = New-ScheduledTaskTrigger -AtStartup
        $trigger.Repetition = (New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 5)).Repetition
        
        $settings = New-ScheduledTaskSettingsSet `
            -AllowStartIfOnBatteries `
            -DontStopIfGoingOnBatteries `
            -StartWhenAvailable `
            -DontStopOnIdleEnd `
            -ExecutionTimeLimit (New-TimeSpan -Hours 0)
        
        # Principal - foloseste utilizatorul curent cu privilegii maxime
        $currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
        $principal = New-ScheduledTaskPrincipal `
            -UserId $currentUser `
            -LogonType Interactive `
            -RunLevel Highest
        
        Register-ScheduledTask `
            -TaskName $taskName `
            -Action $action `
            -Trigger $trigger `
            -Settings $settings `
            -Principal $principal `
            -Description "CasehugBot - Tracking individual per cont (verificare la 5 minute)" `
            -Force | Out-Null
        
        Write-Host "Task Scheduler instalat cu succes!" -ForegroundColor Green
        Write-Host ""
        Write-Host "Detalii:" -ForegroundColor Cyan
        Write-Host "  Nume: $taskName"
        Write-Host "  Trigger: La pornire + repetare la 5 minute"
        Write-Host "  Script: $scriptPath"
        Write-Host ""
        
        return $true
    }
    catch {
        Write-Host "Eroare instalare: $_" -ForegroundColor Red
        return $false
    }
}

function Uninstall-Task {
    Write-Host "Dezinstalare Task Scheduler..." -ForegroundColor Yellow
    
    $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($task) {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
        Write-Host "Task sters cu succes!" -ForegroundColor Green
    }
    else {
        Write-Host "Task-ul nu exista" -ForegroundColor Yellow
    }
}

function Start-TaskManual {
    Write-Host "Pornire task..." -ForegroundColor Yellow
    
    $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($task) {
        Start-ScheduledTask -TaskName $taskName
        Write-Host "Task pornit!" -ForegroundColor Green
    }
    else {
        Write-Host "Task-ul nu exista!" -ForegroundColor Red
    }
}

function Show-Status {
    $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    
    if ($task) {
        $info = Get-ScheduledTaskInfo -TaskName $taskName
        
        Write-Host ""
        Write-Host "STATUS TASK SCHEDULER" -ForegroundColor Cyan
        Write-Host "Nume: $($task.TaskName)" -ForegroundColor White
        Write-Host "Status: $($task.State)" -ForegroundColor White
        Write-Host "Ultima rulare: $($info.LastRunTime)" -ForegroundColor White
        Write-Host "Urmatoare rulare: $($info.NextRunTime)" -ForegroundColor White
        Write-Host ""
    }
    else {
        Write-Host ""
        Write-Host "Task-ul nu este instalat" -ForegroundColor Yellow
        Write-Host "Ruleaza: .\install_task_new.ps1 install" -ForegroundColor Cyan
        Write-Host ""
    }
}

# MAIN
Write-Host ""
Write-Host "CASEHUGBOT SCHEDULER - TASK INSTALLER" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Administrator)) {
    Write-Host "EROARE: Acest script necesita privilegii de Administrator!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Solutie:" -ForegroundColor Yellow
    Write-Host "  1. Inchide fereastra PowerShell"
    Write-Host "  2. Click dreapta pe PowerShell"
    Write-Host "  3. Selecteaza Run as Administrator"
    Write-Host "  4. Ruleaza din nou scriptul"
    Write-Host ""
    exit 1
}

switch ($Action.ToLower()) {
    "install" {
        if (Install-Task) {
            Write-Host "Instalare completata!" -ForegroundColor Green
            Write-Host ""
            Write-Host "NEXT STEPS:" -ForegroundColor Cyan
            Write-Host "  1. Task-ul va porni automat la restart"
            Write-Host "  2. Sau porneste manual: .\install_task_new.ps1 start"
            Write-Host ""
        }
    }
    "uninstall" {
        Uninstall-Task
    }
    "start" {
        Start-TaskManual
    }
    "status" {
        Show-Status
    }
    default {
        Show-Status
    }
}
