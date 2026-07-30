# ================================================================
# WORDLIB Setup Step 6 -- Create Desktop Shortcut (with fun icon)
# Creates a Desktop shortcut to RUN_ME.bat using config\mainbrain_icon.ico.
# One-time run. No admin rights needed. Safe to re-run (overwrites the
# shortcut, never touches wordlib data).
#
# GOLDEN RULE compliance (see CLAUDE_BRIEFING.md):
#   - never hardcodes a drive letter -- uses $PSScriptRoot
#   - zero manual steps after double-click
#   - no emoji in this file (PowerShell-safe, plain ASCII only)
# ================================================================

$ErrorActionPreference = "Stop"

$Root      = Split-Path -Parent $PSScriptRoot          # wordlib root, whatever the drive letter
$Target    = Join-Path $Root "RUN_ME.bat"
$IconPath  = Join-Path $Root "config\mainbrain_icon.ico"
$Desktop   = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $Desktop "WORDLIB - MAINBRAIN.lnk"

if (-not (Test-Path $Target)) {
    Write-Host "[ERR] RUN_ME.bat not found at $Target" -ForegroundColor Red
    Write-Host "      Run this from Setup\ inside the real wordlib folder." -ForegroundColor Yellow
    exit 1
}
if (-not (Test-Path $IconPath)) {
    Write-Host "[WARN] icon missing at $IconPath -- shortcut will use the default .bat icon" -ForegroundColor Yellow
    $IconPath = $Target
}

$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath       = $Target
$Shortcut.WorkingDirectory = $Root
$Shortcut.IconLocation     = "$IconPath,0"
$Shortcut.Description      = "WORDLIB / MAINBRAIN -- one-click launcher"
$Shortcut.Save()

Write-Host ""
Write-Host " =====================================================" -ForegroundColor Cyan
Write-Host "   WORDLIB Setup [6/6] -- Desktop Shortcut" -ForegroundColor Cyan
Write-Host " =====================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "[OK] Shortcut created: $ShortcutPath" -ForegroundColor Green
Write-Host "[OK] Icon: $IconPath" -ForegroundColor Green
Write-Host ""
Write-Host "Double-click the new Desktop icon any time to launch WORDLIB." -ForegroundColor White
