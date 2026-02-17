# -----------------------------------------------------------------------------
# O.R.I.O.N. Unified Launcher -- Start Gateway + Brain together
#
# Usage:
#   .\bin\start.ps1                     # Start everything
#   .\bin\start.ps1 -DevMode            # Start in dev mode
#   .\bin\start.ps1 -NoBrain            # Gateway only (no Python brain)
#   .\bin\start.ps1 -TrustMode          # Skip action confirmations
# -----------------------------------------------------------------------------
param(
    [switch]$DevMode,
    [switch]$NoBrain,
    [switch]$TrustMode,
    [switch]$NoDream,
    [switch]$NoVision,
    [switch]$NoScout
)

$ErrorActionPreference = "Stop"

function Test-Command { param($cmd) return [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }

# -- Resolve project root ------------------------------------------------------
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

# -- Verify build exists -------------------------------------------------------
if (-not (Test-Path "dist/entry.js")) {
    Write-Host "  [O.R.I.O.N.] Build not found. Run prebuild first:" -ForegroundColor Red
    Write-Host "    powershell -ExecutionPolicy Bypass -File bin\prebuild.ps1" -ForegroundColor Cyan
    exit 1
}

Write-Host ""
Write-Host "  +=======================================================+" -ForegroundColor Cyan
Write-Host "  |                                                       |" -ForegroundColor Cyan
Write-Host "  |         O.R.I.O.N. -- Starting All Systems            |" -ForegroundColor Cyan
Write-Host "  |                                                       |" -ForegroundColor Cyan
Write-Host "  +=======================================================+" -ForegroundColor Cyan
Write-Host ""

# -- Ensure Ollama is running --------------------------------------------------
if (Test-Command "ollama") {
    try {
        $null = ollama list 2>&1
        if ($LASTEXITCODE -ne 0) { throw "not running" }
        Write-Host "  [O.R.I.O.N.] Ollama is running" -ForegroundColor Green
    } catch {
        Write-Host "  [O.R.I.O.N.] Starting Ollama..." -ForegroundColor Cyan
        Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden
        Start-Sleep -Seconds 3
        Write-Host "  [O.R.I.O.N.] Ollama started" -ForegroundColor Green
    }
} else {
    Write-Host "  [O.R.I.O.N.] Ollama not installed. LLM features will be limited." -ForegroundColor Yellow
}

# -- Start Python Brain (background) ------------------------------------------
$brainProcess = $null
if (-not $NoBrain) {
    # Prefer Python 3.12 over 3.14+ (ChromaDB/Pydantic v1 is broken on 3.14)
    $pythonCmd = $null
    if (Test-Command "py") {
        # Windows py launcher: try 3.12 first, then 3.11, then 3.13
        foreach ($pyVer in @("3.12", "3.11", "3.13")) {
            try {
                $testOut = & py "-$pyVer" --version 2>&1
                if ($LASTEXITCODE -eq 0) {
                    $pythonCmd = "py"
                    $script:pyVerFlag = "-$pyVer"
                    Write-Host "  [O.R.I.O.N.] Using Python $pyVer (via py launcher)" -ForegroundColor Green
                    break
                }
            } catch {}
        }
    }
    if (-not $pythonCmd) {
        foreach ($cmd in @("python3", "python", "py")) {
            if (Test-Command $cmd) { $pythonCmd = $cmd; break }
        }
    }

    if ($pythonCmd) {
        Write-Host "  [O.R.I.O.N.] Starting Python Brain..." -ForegroundColor Cyan

        $brainArgs = @()
        if ($script:pyVerFlag) { $brainArgs += $script:pyVerFlag }
        $brainArgs += "scripts/orion_brain.py"
        if ($TrustMode) { $brainArgs += "--trust-mode" }
        if ($NoDream)   { $brainArgs += "--no-dream" }
        if ($NoVision)  { $brainArgs += "--no-vision" }
        if ($NoScout)   { $brainArgs += "--no-scout" }

        $brainProcess = Start-Process -FilePath $pythonCmd -ArgumentList $brainArgs `
            -WorkingDirectory $ProjectRoot -WindowStyle Normal -PassThru

        Write-Host ("  [O.R.I.O.N.] Brain started (PID: " + $brainProcess.Id + ")") -ForegroundColor Green
        Write-Host ("  [O.R.I.O.N.] Brain health: http://127.0.0.1:18790/") -ForegroundColor Cyan
    } else {
        Write-Host "  [O.R.I.O.N.] Python not found. Brain subsystems disabled." -ForegroundColor Yellow
    }
} else {
    Write-Host "  [O.R.I.O.N.] Brain disabled (-NoBrain flag)" -ForegroundColor Yellow
}

Write-Host ""

# -- Start Node.js Gateway (foreground) ----------------------------------------
Write-Host "  [O.R.I.O.N.] Starting Gateway..." -ForegroundColor Cyan

$gatewayArgs = @("openclaw.mjs", "gateway", "run")
if ($DevMode) { $gatewayArgs += "--dev" }

Write-Host ""
Write-Host "  Gateway  : http://localhost:18789/" -ForegroundColor White
Write-Host "  Brain    : http://127.0.0.1:18790/" -ForegroundColor White
Write-Host "  Press Ctrl+C to stop all systems." -ForegroundColor White
Write-Host ""

try {
    # Run gateway in foreground -- blocks until Ctrl+C
    & node $gatewayArgs
} finally {
    # When gateway exits, also stop the brain
    if ($brainProcess -and -not $brainProcess.HasExited) {
        Write-Host ""
        Write-Host "  [O.R.I.O.N.] Stopping Brain (PID: $($brainProcess.Id))..." -ForegroundColor Yellow
        Stop-Process -Id $brainProcess.Id -Force -ErrorAction SilentlyContinue
        Write-Host "  [O.R.I.O.N.] Brain stopped." -ForegroundColor Green
    }
    Write-Host "  [O.R.I.O.N.] All systems shut down." -ForegroundColor Green
}
