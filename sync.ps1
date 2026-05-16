# sync.ps1 — Pull latest changes from GitHub and run the crawler if updated.
# Designed to be run by Windows Task Scheduler on a schedule.

param(
    [string]$RepoDir   = $PSScriptRoot,
    [string]$OutputDir = "$PSScriptRoot\pdfs",
    [int]   $Years     = 2,
    [switch]$PdfsOnly
)

$logFile = "$RepoDir\sync.log"

function Log($msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$ts  $msg" | Tee-Object -FilePath $logFile -Append
}

Log "--- Sync started ---"
Set-Location $RepoDir

# ── 1. Fetch remote changes ──────────────────────────────────────────────────
Log "Fetching from origin..."
git fetch origin main 2>&1 | ForEach-Object { Log $_ }

$behind = git rev-list HEAD..origin/main --count 2>$null
if ($LASTEXITCODE -ne 0) {
    Log "ERROR: git rev-list failed. Is this a git repo with a remote set?"
    exit 1
}

if ([int]$behind -eq 0) {
    Log "Already up to date. No pull needed."
} else {
    Log "Pulling $behind new commit(s)..."
    git pull origin main 2>&1 | ForEach-Object { Log $_ }
    Log "Pull complete."
}

# ── 2. Run the crawler to download new files ─────────────────────────────────
Log "Running crawler (last $Years years)..."

$crawlerArgs = @(
    "$RepoDir\crawl_hpcuserforum.py",
    "--download",
    "--years", $Years,
    "--output", $OutputDir,
    "--no-wayback"   # skip CDX for scheduled runs; live crawl is sufficient
)
if ($PdfsOnly) { $crawlerArgs += "--pdfs-only" }

python @crawlerArgs 2>&1 | ForEach-Object { Log $_ }

Log "--- Sync complete ---"
Log ""
