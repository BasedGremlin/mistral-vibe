# ============================================================
# USB AI MASTER - LM Studio Setup Launcher
# For: Johannes
# Version: 3.0 - Merged (USB AI + Consolidated AI Master)
# OS: Windows 11 (compatible with Windows 10)
#
# WHAT THIS SCRIPT DOES:
#   - Auto-detects LM Studio across 4 install paths + registry
#   - Copies GGUF models from USB /models to host LM Studio cache
#   - Writes all 4 presets to LM Studio presets directory
#   - Creates timestamped backup before any write
#   - Launches LM Studio on completion
#
# ENCODING RULE: NO emoji, NO Unicode symbols. Pure ASCII only.
# Use [OK], [WARN], [ERR] not checkmarks or icons.
# This script must always be generated/edited via HTML_Generator.html
# to prevent invisible Unicode corruption.
# ============================================================

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

# ============================================================
# DETECT USB ROOT
# $PSScriptRoot = the /src folder this script lives in.
# Parent of that = USB root. Works regardless of drive letter.
# ============================================================
$USB_ROOT    = Split-Path -Parent $PSScriptRoot
$MODELS_USB  = Join-Path $USB_ROOT "models"
$PRESETS_USB = Join-Path $USB_ROOT "presets"
$CONFIG_USB  = Join-Path $USB_ROOT "config"
$BACKUP_DIR  = Join-Path $USB_ROOT "backups\Backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
$LOG_FILE    = "$env:USERPROFILE\Desktop\USB_AI_Master_Log.txt"

# ============================================================
# HOST PATHS (LM Studio)
# ============================================================
$LMStudioPaths = @(
    "$env:LOCALAPPDATA\Programs\LM-Studio\LM Studio.exe",
    "$env:ProgramFiles\LM Studio\LM Studio.exe",
    "${env:ProgramFiles(x86)}\LM Studio\LM Studio.exe",
    "$env:LOCALAPPDATA\LM-Studio\LM Studio.exe"
)

$PresetDir   = "$env:APPDATA\LM Studio\presets"
$ModelCache1 = "$env:USERPROFILE\.cache\lm-studio\models"
$ModelCache2 = "$env:LOCALAPPDATA\LM-Studio\models"

# ============================================================
# LOGGING
# ============================================================
function Write-Log {
    param([string]$Msg, [string]$Lvl = "INFO")
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $LOG_FILE -Value "[$ts][$Lvl] $Msg" -ErrorAction SilentlyContinue
}

# ============================================================
# FIND LM STUDIO
# 4-path search + registry fallback.
# ============================================================
function Get-LMSPath {
    foreach ($p in $LMStudioPaths) {
        if (Test-Path $p) { return $p }
    }
    try {
        $reg = Get-ItemProperty "HKCU:\Software\LM-Studio" -ErrorAction SilentlyContinue
        if ($reg -and (Test-Path $reg.InstallPath)) { return $reg.InstallPath }
    } catch {}
    return $null
}

# ============================================================
# MODEL STATUS CHECK
# Scans host LM Studio cache folders for the 4 recommended models.
# ============================================================
function Get-ModelStatus {
    $modelList = @(
        @{ Name = "Dolphin 2.9 Mistral 7B";  Search = "dolphin-2.9-mistral" },
        @{ Name = "Dolphin 2.8 Llama 3 8B";  Search = "dolphin-2.8-llama3" },
        @{ Name = "Qwen 2.5 Coder 7B";        Search = "qwen2.5-coder-7b"   },
        @{ Name = "Llama 3 8B Instruct";       Search = "Llama-3-8B-Instruct" }
    )

    $cacheDirs = @($ModelCache1, $ModelCache2) | Where-Object { Test-Path $_ }
    $result = @()

    foreach ($m in $modelList) {
        $found = $false
        foreach ($d in $cacheDirs) {
            if (Get-ChildItem $d -Recurse -Filter "*.gguf" -ErrorAction SilentlyContinue |
                Where-Object { $_.Name -like "*$($m.Search)*" }) {
                $found = $true; break
            }
        }
        $onUSB = $false
        if (Test-Path $MODELS_USB) {
            $onUSB = [bool](Get-ChildItem $MODELS_USB -Filter "*.gguf" -ErrorAction SilentlyContinue |
                           Where-Object { $_.Name -like "*$($m.Search)*" })
        }
        $result += @{ Name = $m.Name; FoundOnHost = $found; FoundOnUSB = $onUSB }
    }
    return $result
}

# ============================================================
# COPY MODELS FROM USB TO HOST
# Copies all .gguf files from USB /models to host LM Studio cache.
# ============================================================
function Copy-ModelsFromUSB {
    param($LogCallback)

    if (-not (Test-Path $MODELS_USB)) {
        & $LogCallback "No models folder found on USB at: $MODELS_USB" "warn"
        return 0
    }

    $targetDir = $ModelCache1
    if (-not (Test-Path $targetDir)) {
        New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
    }

    $models = Get-ChildItem $MODELS_USB -Filter "*.gguf" -ErrorAction SilentlyContinue
    if (-not $models) {
        & $LogCallback "No GGUF model files found in USB /models folder." "warn"
        & $LogCallback "See MODEL_GUIDE.txt in /docs for download instructions." "info"
        return 0
    }

    $copied = 0
    foreach ($m in $models) {
        $dest = Join-Path $targetDir $m.Name
        if (Test-Path $dest) {
            & $LogCallback "Already on host: $($m.Name)" "ok"
        } else {
            & $LogCallback "Copying: $($m.Name) (may take several minutes)..." "step"
            try {
                Copy-Item $m.FullName $dest -Force
                & $LogCallback "Copied: $($m.Name)" "ok"
                $copied++
            } catch {
                & $LogCallback "Failed to copy $($m.Name): $_" "err"
            }
        }
    }
    return $copied
}

# ============================================================
# WRITE PRESETS TO HOST
# Writes all JSON preset files from USB /presets to LM Studio.
# ============================================================
function Set-AllPresets {
    param($LogCallback)

    if (-not (Test-Path $PresetDir)) {
        New-Item -ItemType Directory -Path $PresetDir -Force | Out-Null
    }

    if (-not (Test-Path $PRESETS_USB)) {
        & $LogCallback "Presets folder not found on USB at: $PRESETS_USB" "err"
        return $false
    }

    $presets = Get-ChildItem $PRESETS_USB -Filter "*.json" -ErrorAction SilentlyContinue
    if (-not $presets) {
        & $LogCallback "No JSON preset files found in USB /presets folder." "warn"
        return $false
    }

    $written = 0
    foreach ($p in $presets) {
        $dest = Join-Path $PresetDir $p.Name
        try {
            Copy-Item $p.FullName $dest -Force
            & $LogCallback "Preset written: $($p.Name)" "ok"
            $written++
        } catch {
            & $LogCallback "Failed to write preset $($p.Name): $_" "err"
        }
    }
    return ($written -gt 0)
}

# ============================================================
# BACKUP (always before any write -- non-negotiable)
# ============================================================
function New-Backup {
    param($LogCallback)
    try {
        New-Item -ItemType Directory -Path $BACKUP_DIR -Force | Out-Null
        if (Test-Path $PresetDir) {
            Get-ChildItem $PresetDir -Filter "*.json" -ErrorAction SilentlyContinue |
                ForEach-Object { Copy-Item $_.FullName $BACKUP_DIR -ErrorAction SilentlyContinue }
        }
        & $LogCallback "Backup created: $BACKUP_DIR" "ok"
        Write-Log "Backup at $BACKUP_DIR"
        return $true
    } catch {
        & $LogCallback "Backup failed (non-fatal): $_" "warn"
        return $false
    }
}

# ============================================================
# COLOURS (dark theme, pure .NET named colours -- no hex)
# ============================================================
$colDark  = [System.Drawing.Color]::FromArgb(18, 18, 28)
$colPanel = [System.Drawing.Color]::FromArgb(22, 22, 38)
$colCard  = [System.Drawing.Color]::FromArgb(30, 30, 50)
$colText  = [System.Drawing.Color]::FromArgb(220, 220, 240)
$colMuted = [System.Drawing.Color]::FromArgb(130, 130, 160)
$colBlue  = [System.Drawing.Color]::FromArgb(99,  179, 237)
$colGreen = [System.Drawing.Color]::FromArgb(72,  199, 142)
$colWarn  = [System.Drawing.Color]::FromArgb(246, 224, 94)
$colRed   = [System.Drawing.Color]::FromArgb(252, 129, 129)
$colGold  = [System.Drawing.Color]::FromArgb(246, 173, 85)

$fTitle = New-Object System.Drawing.Font("Segoe UI", 18, [System.Drawing.FontStyle]::Bold)
$fSub   = New-Object System.Drawing.Font("Segoe UI", 10)
$fBold  = New-Object System.Drawing.Font("Segoe UI", 10, [System.Drawing.FontStyle]::Bold)
$fSmall = New-Object System.Drawing.Font("Segoe UI",  9)
$fMono  = New-Object System.Drawing.Font("Consolas",  9)
$fBtn   = New-Object System.Drawing.Font("Segoe UI", 11, [System.Drawing.FontStyle]::Bold)

# ============================================================
# MAIN FORM
# ============================================================
$form = New-Object System.Windows.Forms.Form
$form.Text = "USB AI Master - LM Studio Setup"
$form.Size = New-Object System.Drawing.Size(720, 800)
$form.StartPosition = "CenterScreen"
$form.BackColor = $colDark
$form.FormBorderStyle = "FixedSingle"
$form.MaximizeBox = $false

# TITLE
$lblTitle = New-Object System.Windows.Forms.Label
$lblTitle.Text = "USB AI Master"
$lblTitle.Font = $fTitle
$lblTitle.ForeColor = $colGold
$lblTitle.Location = New-Object System.Drawing.Point(20, 20)
$lblTitle.Size = New-Object System.Drawing.Size(400, 40)
$form.Controls.Add($lblTitle)

$lblSub = New-Object System.Windows.Forms.Label
$lblSub.Text = "LM Studio Setup  --  Portable AI Databank  --  For: Johannes"
$lblSub.Font = $fSmall
$lblSub.ForeColor = $colMuted
$lblSub.Location = New-Object System.Drawing.Point(22, 62)
$lblSub.Size = New-Object System.Drawing.Size(660, 20)
$form.Controls.Add($lblSub)

# DIVIDER
$div = New-Object System.Windows.Forms.Label
$div.BackColor = $colCard
$div.Location = New-Object System.Drawing.Point(20, 90)
$div.Size = New-Object System.Drawing.Size(672, 2)
$form.Controls.Add($div)

# ── STATUS CARDS ──────────────────────────────────────────────
function New-Card {
    param($y, $icon, $label, $detail)

    $card = New-Object System.Windows.Forms.Panel
    $card.Location = New-Object System.Drawing.Point(20, $y)
    $card.Size = New-Object System.Drawing.Size(672, 68)
    $card.BackColor = $colCard
    $form.Controls.Add($card)

    $ico = New-Object System.Windows.Forms.Label
    $ico.Text = $icon
    $ico.Font = $fBold
    $ico.ForeColor = $colBlue
    $ico.Location = New-Object System.Drawing.Point(14, 10)
    $ico.Size = New-Object System.Drawing.Size(200, 20)
    $card.Controls.Add($ico)

    $status = New-Object System.Windows.Forms.Label
    $status.Text = "Checking..."
    $status.Font = $fBold
    $status.ForeColor = $colMuted
    $status.Location = New-Object System.Drawing.Point(460, 10)
    $status.Size = New-Object System.Drawing.Size(196, 20)
    $status.TextAlign = "MiddleRight"
    $card.Controls.Add($status)

    $det = New-Object System.Windows.Forms.Label
    $det.Text = $detail
    $det.Font = $fSmall
    $det.ForeColor = $colMuted
    $det.Location = New-Object System.Drawing.Point(14, 36)
    $det.Size = New-Object System.Drawing.Size(644, 22)
    $card.Controls.Add($det)

    return @{ Status = $status; Detail = $det }
}

$c1 = New-Card 102 "[1] LM Studio" "Is LM Studio installed on this PC?" ""
$c2 = New-Card 180 "[2] Presets"   "Have the 4 AI presets been applied?" ""
$c3 = New-Card 258 "[3] USB Models" "Are GGUF model files on this USB drive?" ""
$c4 = New-Card 336 "[4] Host Models" "Are models installed on this PC for LM Studio?" ""

$l1Status = $c1.Status; $l1Detail = $c1.Detail
$l2Status = $c2.Status; $l2Detail = $c2.Detail
$l3Status = $c3.Status; $l3Detail = $c3.Detail
$l4Status = $c4.Status; $l4Detail = $c4.Detail

# ── LOG PANEL ────────────────────────────────────────────────
$lblLog = New-Object System.Windows.Forms.Label
$lblLog.Text = "Activity Log"
$lblLog.Font = $fBold
$lblLog.ForeColor = $colMuted
$lblLog.Location = New-Object System.Drawing.Point(20, 424)
$lblLog.Size = New-Object System.Drawing.Size(200, 20)
$form.Controls.Add($lblLog)

$txtLog = New-Object System.Windows.Forms.RichTextBox
$txtLog.Size = New-Object System.Drawing.Size(672, 220)
$txtLog.Location = New-Object System.Drawing.Point(20, 448)
$txtLog.BackColor = $colPanel
$txtLog.ForeColor = $colText
$txtLog.Font = $fMono
$txtLog.ReadOnly = $true
$txtLog.BorderStyle = "None"
$txtLog.ScrollBars = "Vertical"
$form.Controls.Add($txtLog)

# LOG FUNCTION
function Add-Log {
    param([string]$msg, [string]$type = "info")
    $ts  = Get-Date -Format "HH:mm:ss"
    $pre = switch ($type) {
        "ok"   { "[OK]   " }
        "warn" { "[WARN] " }
        "err"  { "[ERR]  " }
        "step" { "[----] " }
        "info" { "[INFO] " }
        default{ "[INFO] " }
    }
    $txtLog.AppendText("[$ts] $pre $msg`n")
    $txtLog.ScrollToCaret()
    Write-Log "$type | $msg"
}

# ── BUTTONS ──────────────────────────────────────────────────
$btnCheck = New-Object System.Windows.Forms.Button
$btnCheck.Text = "Refresh Checks"
$btnCheck.Size = New-Object System.Drawing.Size(175, 44)
$btnCheck.Location = New-Object System.Drawing.Point(20, 684)
$btnCheck.BackColor = $colCard
$btnCheck.ForeColor = $colBlue
$btnCheck.Font = $fBold
$btnCheck.FlatStyle = "Flat"
$btnCheck.FlatAppearance.BorderColor = $colBlue
$form.Controls.Add($btnCheck)

$btnInstall = New-Object System.Windows.Forms.Button
$btnInstall.Text = "ONE-CLICK SETUP + COPY MODELS"
$btnInstall.Size = New-Object System.Drawing.Size(380, 52)
$btnInstall.Location = New-Object System.Drawing.Point(205, 680)
$btnInstall.BackColor = $colGold
$btnInstall.ForeColor = $colDark
$btnInstall.Font = $fBtn
$btnInstall.FlatStyle = "Flat"
$btnInstall.FlatAppearance.BorderSize = 0
$form.Controls.Add($btnInstall)

$btnLog = New-Object System.Windows.Forms.Button
$btnLog.Text = "Open Log"
$btnLog.Size = New-Object System.Drawing.Size(100, 44)
$btnLog.Location = New-Object System.Drawing.Point(600, 684)
$btnLog.BackColor = $colCard
$btnLog.ForeColor = $colMuted
$btnLog.Font = $fSmall
$btnLog.FlatStyle = "Flat"
$btnLog.FlatAppearance.BorderColor = $colCard
$form.Controls.Add($btnLog)

# HINT
$lblHint = New-Object System.Windows.Forms.Label
$lblHint.Text = "To download missing models: open LM Studio > Search tab > type model name + gguf q4"
$lblHint.Font = $fSmall
$lblHint.ForeColor = $colWarn
$lblHint.Location = New-Object System.Drawing.Point(20, 740)
$lblHint.Size = New-Object System.Drawing.Size(675, 30)
$lblHint.Visible = $false
$form.Controls.Add($lblHint)

# ============================================================
# RUN CHECKS
# ============================================================
function Invoke-Checks {
    Add-Log "Running system checks..." "step"

    $lp = Get-LMSPath
    if ($lp) {
        $l1Status.Text = "FOUND"; $l1Status.ForeColor = $colGreen
        $l1Detail.Text = $lp
        Add-Log "LM Studio found: $lp" "ok"
    } else {
        $l1Status.Text = "NOT FOUND"; $l1Status.ForeColor = $colRed
        $l1Detail.Text = "Install LM Studio from lmstudio.ai then re-run checks"
        Add-Log "LM Studio not found. Install from lmstudio.ai" "err"
    }

    $presetCount = 0
    if (Test-Path $PresetDir) {
        $presetCount = (Get-ChildItem $PresetDir -Filter "*Gold*" -ErrorAction SilentlyContinue).Count +
                       (Get-ChildItem $PresetDir -Filter "*Dolphin*" -ErrorAction SilentlyContinue).Count +
                       (Get-ChildItem $PresetDir -Filter "*Coding*" -ErrorAction SilentlyContinue).Count +
                       (Get-ChildItem $PresetDir -Filter "*General*" -ErrorAction SilentlyContinue).Count
    }
    if ($presetCount -gt 0) {
        $l2Status.Text = "APPLIED ($presetCount)"; $l2Status.ForeColor = $colGreen
        $l2Detail.Text = "$presetCount preset(s) in $PresetDir"
        Add-Log "Presets: $presetCount applied on host" "ok"
    } else {
        $l2Status.Text = "MISSING"; $l2Status.ForeColor = $colWarn
        $l2Detail.Text = "Click ONE-CLICK SETUP to write presets from USB"
        Add-Log "Presets not yet applied. Click install." "warn"
    }

    $usbModels = 0
    if (Test-Path $MODELS_USB) {
        $usbModels = (Get-ChildItem $MODELS_USB -Filter "*.gguf" -ErrorAction SilentlyContinue).Count
    }
    if ($usbModels -gt 0) {
        $l3Status.Text = "$usbModels GGUF FOUND"; $l3Status.ForeColor = $colGreen
        $l3Detail.Text = "$MODELS_USB"
        Add-Log "USB models: $usbModels GGUF file(s) ready to copy" "ok"
    } else {
        $l3Status.Text = "EMPTY"; $l3Status.ForeColor = $colWarn
        $l3Detail.Text = "Add GGUF model files to: $MODELS_USB"
        Add-Log "No models on USB. Download via LM Studio > Search tab." "warn"
    }

    $modelRes = Get-ModelStatus
    $hostFound = ($modelRes | Where-Object { $_.FoundOnHost }).Count
    $anyMissing = $hostFound -lt $modelRes.Count
    if ($hostFound -gt 0) {
        $l4Status.Text = "$hostFound/4 OK"
        $l4Status.ForeColor = if ($anyMissing) { $colWarn } else { $colGreen }
        $l4Detail.Text = "$hostFound of 4 recommended models found on this PC"
        Add-Log "Host models: $hostFound of 4 found" "ok"
    } else {
        $l4Status.Text = "NONE"; $l4Status.ForeColor = $colRed
        $l4Detail.Text = "No models on this PC. Install will copy from USB."
        Add-Log "No models on host. Click install to copy from USB." "warn"
    }

    $lblHint.Visible = $anyMissing
    Add-Log "Checks complete." "info"
}

# ============================================================
# ONE-CLICK INSTALL
# ============================================================
$btnInstall.Add_Click({
    $btnInstall.Enabled = $false
    $btnInstall.Text = "Working - please wait..."

    Add-Log "==============================" "step"
    Add-Log "Starting USB AI Master setup..." "step"

    Add-Log "Step 1/4 - Creating backup of existing presets..." "step"
    New-Backup { param($m,$t) Add-Log $m $t } | Out-Null

    Add-Log "Step 2/4 - Writing presets from USB to this PC..." "step"
    $presetOK = Set-AllPresets { param($m,$t) Add-Log $m $t }
    if (-not $presetOK) {
        Add-Log "Preset write failed. Try Run as Administrator." "err"
        [System.Windows.Forms.MessageBox]::Show(
            "Could not write presets.`nRight-click RUN_ME.bat and select Run as Administrator.",
            "Error", "OK", "Error")
        $btnInstall.Enabled = $true
        $btnInstall.Text = "ONE-CLICK SETUP + COPY MODELS"
        return
    }

    Add-Log "Step 3/4 - Copying models from USB to this PC..." "step"
    Add-Log "Large models (4-5 GB each) may take 5-20 minutes." "info"
    $copied = Copy-ModelsFromUSB { param($m,$t) Add-Log $m $t }
    Add-Log "Models copied this session: $copied new file(s)" "ok"

    Add-Log "Step 4/4 - Launching LM Studio..." "step"
    $lp = Get-LMSPath
    if ($lp) {
        Start-Process $lp
        Add-Log "LM Studio launched: $lp" "ok"
    } else {
        Add-Log "LM Studio not found. Open it manually from Start menu." "warn"
    }

    Add-Log "==============================" "step"
    Add-Log "SETUP COMPLETE." "ok"
    Add-Log "In LM Studio: Chat tab > Preset > choose your preset." "info"
    Add-Log "Recommended start: Dolphin - Uncensored Assistant" "info"

    $btnInstall.Text = "DONE!"
    $btnInstall.BackColor = $colGreen
    Invoke-Checks

    [System.Windows.Forms.MessageBox]::Show(
        "Setup complete!`n`n" +
        "In LM Studio:`n" +
        "1. Click Chat tab`n" +
        "2. Click Preset`n" +
        "3. Choose a preset:`n" +
        "   - Dolphin Uncensored    (everyday, unrestricted)`n" +
        "   - Gold Standard          (teaching, classroom)`n" +
        "   - Coding Assistant       (code and scripts)`n" +
        "   - General Assistant      (balanced, everyday)`n`n" +
        "Log saved to Desktop: USB_AI_Master_Log.txt",
        "USB AI Master - Done!", "OK", "Information")
})

$btnCheck.Add_Click({ Add-Log "Manual refresh..." "step"; Invoke-Checks })

$btnLog.Add_Click({
    if (Test-Path $LOG_FILE) { Start-Process notepad.exe $LOG_FILE }
    else { [System.Windows.Forms.MessageBox]::Show("No log yet. Run install first.","Log","OK","Information") }
})

$form.Add_Shown({
    Add-Log "USB AI Master LM Studio Launcher started." "info"
    Add-Log "USB root detected: $USB_ROOT" "info"
    Add-Log "Log file: $LOG_FILE" "info"
    Invoke-Checks
})

[void]$form.ShowDialog()
