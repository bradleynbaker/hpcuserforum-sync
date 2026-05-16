# install-task.ps1 — Register a Windows Scheduled Task that runs sync.ps1 daily.
# Run this once as Administrator.

param(
    [string]$RepoDir   = $PSScriptRoot,
    [string]$OutputDir = "$PSScriptRoot\pdfs",
    [int]   $Years     = 2,
    [switch]$PdfsOnly,
    [string]$TaskName  = "HPCUserForum-Sync",
    [string]$RunAt     = "06:00"   # daily at 6 AM
)

$extraArgs = if ($PdfsOnly) { " -PdfsOnly" } else { "" }

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NonInteractive -ExecutionPolicy Bypass -File `"$RepoDir\sync.ps1`" -RepoDir `"$RepoDir`" -OutputDir `"$OutputDir`" -Years $Years$extraArgs"

$trigger = New-ScheduledTaskTrigger -Daily -At $RunAt

$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable

# Remove existing task if present
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed existing task: $TaskName"
}

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -RunLevel Highest `
    -Description "Pull latest hpcuserforum-sync repo and download new PDFs"

Write-Host ""
Write-Host "Task '$TaskName' registered. Runs daily at $RunAt."
Write-Host "Logs will appear in: $RepoDir\sync.log"
Write-Host ""
Write-Host "To run it immediately:"
Write-Host "  Start-ScheduledTask -TaskName '$TaskName'"
Write-Host ""
Write-Host "To remove it:"
Write-Host "  Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"
