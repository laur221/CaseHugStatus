# CasehugBot Task Scheduler - Automatic Installation
# Run as Administrator: Right-click -> Run as Administrator

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
    Write-Host "Installing Task Scheduler..." -ForegroundColor Yellow
    
    if (-not (Test-Path $scriptPath)) {
        Write-Host "Error: $scriptPath does not exist!" -ForegroundColor Red
        return $false
    }
    
    $existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($existingTask) {
        Write-Host "Removing existing task..." -ForegroundColor Yellow
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    }
    
    try {
        # Use wscript.exe to run VBScript completely hidden
        $wscriptPath = "C:\Windows\System32\wscript.exe"
        $action = New-ScheduledTaskAction -Execute $wscriptPath -Argument "`"$scriptPath`"" -WorkingDirectory $workingDir
        
        $trigger = New-ScheduledTaskTrigger -AtStartup
        $trigger.Repetition = (New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 5)).Repetition
        
        $settings = New-ScheduledTaskSettingsSet `
            -AllowStartIfOnBatteries `
            -DontStopIfGoingOnBatteries `
            -StartWhenAvailable `
            -DontStopOnIdleEnd `
            -MultipleInstances IgnoreNew `
            -ExecutionTimeLimit (New-TimeSpan -Hours 0)
        
        # Principal - use current user with highest privileges
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
            -Description "CasehugBot - Individual per-account tracking (check every 5 minutes)" `
            -Force | Out-Null
        
        Write-Host "Task Scheduler installed successfully!" -ForegroundColor Green
        Write-Host ""
        Write-Host "Details:" -ForegroundColor Cyan
        Write-Host "  Name: $taskName"
        Write-Host "  Trigger: At startup + repeat every 5 minutes"
        Write-Host "  Script: $scriptPath"
        Write-Host ""
        
        return $true
    }
    catch {
        Write-Host "Installation error: $_" -ForegroundColor Red
        return $false
    }
}

function Uninstall-Task {
    Write-Host "Uninstalling Task Scheduler..." -ForegroundColor Yellow
    
    $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($task) {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
        Write-Host "Task removed successfully!" -ForegroundColor Green
    }
    else {
        Write-Host "Task does not exist" -ForegroundColor Yellow
    }
}

function Start-TaskManual {
    Write-Host "Starting task..." -ForegroundColor Yellow
    
    $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if ($task) {
        Start-ScheduledTask -TaskName $taskName
        Write-Host "Task started!" -ForegroundColor Green
    }
    else {
        Write-Host "Task does not exist!" -ForegroundColor Red
    }
}

function Show-Status {
    $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    
    if ($task) {
        $info = Get-ScheduledTaskInfo -TaskName $taskName
        
        Write-Host ""
        Write-Host "TASK SCHEDULER STATUS" -ForegroundColor Cyan
        Write-Host "Name: $($task.TaskName)" -ForegroundColor White
        Write-Host "Status: $($task.State)" -ForegroundColor White
        Write-Host "Last run: $($info.LastRunTime)" -ForegroundColor White
        Write-Host "Next run: $($info.NextRunTime)" -ForegroundColor White
        Write-Host ""
    }
    else {
        Write-Host ""
        Write-Host "Task is not installed" -ForegroundColor Yellow
        Write-Host "Run: .\install_task_new.ps1 install" -ForegroundColor Cyan
        Write-Host ""
    }
}

# MAIN
Write-Host ""
Write-Host "CASEHUGBOT SCHEDULER - TASK INSTALLER" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Administrator)) {
    Write-Host "ERROR: This script requires Administrator privileges!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Solution:" -ForegroundColor Yellow
    Write-Host "  1. Close PowerShell window"
    Write-Host "  2. Right-click on PowerShell"
    Write-Host "  3. Select Run as Administrator"
    Write-Host "  4. Run the script again"
    Write-Host ""
    exit 1
}

switch ($Action.ToLower()) {
    "install" {
        if (Install-Task) {
            Write-Host "Installation complete!" -ForegroundColor Green
            Write-Host ""
            Write-Host "NEXT STEPS:" -ForegroundColor Cyan
            Write-Host "  1. Task will start automatically at restart"
            Write-Host "  2. Or start manually: .\install_task_new.ps1 start"
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
