<#
.SYNOPSIS
  Starts everything this project needs and prints where to find it.
.DESCRIPTION
  1. Checks for node, pnpm and git.
  2. Installs workspace dependencies (skip with -SkipInstall).
  3. Ensures backend/frontend .env files exist (creates from example/defaults).
  4. Regenerates the Prisma contract artifacts (best effort).
  5. Runs the backend test suite as a sanity gate (warns only).
  6. Starts backend + frontend dev servers in their own windows.
  7. Waits for both to answer health checks, then prints all links.
  ai-service is skipped automatically: it is still an empty scaffold with
  no runnable entry point.
.EXAMPLE
  .\run.ps1
.EXAMPLE
  .\run.ps1 -SkipInstall
#>
param(
  [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

$BackendDir = Join-Path $PSScriptRoot "apps\backend"
$FrontendDir = Join-Path $PSScriptRoot "apps\frontend"

function Test-Command($Name) {
  return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Get-BackendPort {
  $port = 5000
  $envFile = Join-Path $BackendDir ".env"
  if (Test-Path -LiteralPath $envFile) {
    foreach ($line in (Get-Content -LiteralPath $envFile)) {
      if ($line -match "^\s*PORT\s*=\s*(\d+)\s*$") { $port = [int]$Matches[1] }
    }
  }
  return $port
}

function Wait-Healthy($Name, $Url, $TimeoutSec = 90) {
  Write-Host "Waiting for $Name ($Url) ..."
  $deadline = (Get-Date).AddSeconds($TimeoutSec)
  while ((Get-Date) -lt $deadline) {
    try {
      $res = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
      if ($res.StatusCode -ge 200 -and $res.StatusCode -lt 500) {
        Write-Host "  $Name is up (HTTP $($res.StatusCode))."
        return $true
      }
    } catch {
      Start-Sleep -Seconds 2
    }
  }
  Write-Warning "$Name did not answer within $TimeoutSec seconds. Check its window for errors."
  return $false
}

# --- 1. Prerequisites -------------------------------------------------------
Write-Host "=== 1/6 Prerequisites ==="
$missing = @()
foreach ($cmd in @("node", "pnpm", "git")) {
  if (Test-Command $cmd) { Write-Host "  [ok] $cmd" }
  else { $missing += $cmd; Write-Host "  [MISSING] $cmd" }
}
if ($missing.Count -gt 0) {
  Write-Error "Missing required tools: $($missing -join ', '). Install them and re-run .\run.ps1"
}

# --- 2. Dependencies --------------------------------------------------------
if ($SkipInstall) {
  Write-Host "=== 2/6 Dependencies (skipped) ==="
} else {
  Write-Host "=== 2/6 Installing dependencies (pnpm install) ==="
  & pnpm install
  if ($LASTEXITCODE -ne 0) { Write-Error "pnpm install failed. Fix the errors above and re-run." }
}

# --- 3. Environment files ---------------------------------------------------
Write-Host "=== 3/6 Environment files ==="
$backendEnv = Join-Path $BackendDir ".env"
if (-not (Test-Path -LiteralPath $backendEnv)) {
  Copy-Item -LiteralPath (Join-Path $BackendDir ".env.example") -Destination $backendEnv
  Write-Warning "Created apps\backend\.env from the example. Fill in DATABASE_URL + Clerk keys, then re-run."
}
$frontendEnv = Join-Path $FrontendDir ".env"
if (-not (Test-Path -LiteralPath $frontendEnv)) {
  Set-Content -LiteralPath $frontendEnv -Value "VITE_API_URL=http://localhost:5000/api/v1`nVITE_CLERK_PUBLISHABLE_KEY=pk_test_...`n"
  Write-Warning "Created apps\frontend\.env with defaults. Set VITE_CLERK_PUBLISHABLE_KEY to match your Clerk app."
}
Write-Host "  [ok] env files present (values never printed)."

# --- 4. Prisma contract -----------------------------------------------------
# NOTE: no 2>&1 here on purpose. Merging a native command's stderr into the
# pipeline wraps each line in an ErrorRecord, which combined with
# $ErrorActionPreference = "Stop" aborts the script on harmless output
# (pnpm echoes the executed command to stderr). Exit code is enough.
Write-Host "=== 4/6 Prisma contract ==="
& pnpm --filter backend exec prisma contract emit
if ($LASTEXITCODE -ne 0) {
  Write-Warning "prisma contract emit failed (DB offline?). Continuing with the checked-in artifacts."
} else {
  Write-Host "  [ok] contract.json / contract.d.ts regenerated."
}

# --- 5. Backend tests (sanity gate, warns only) ------------------------------
Write-Host "=== 5/6 Backend tests ==="
& pnpm --filter backend test
if ($LASTEXITCODE -ne 0) { Write-Warning "Backend tests FAILED. Servers will still start, but fix the tests." }

# --- 6. Dev servers ----------------------------------------------------------
$BackendPort = Get-BackendPort
$FrontendPort = 5173
$ApiBase = "http://localhost:$BackendPort/api/v1"

Write-Host "=== 6/6 Starting servers (each in its own window) ==="
Start-Process powershell -ArgumentList @("-NoExit", "-Command", "Set-Location -LiteralPath '$BackendDir'; pnpm dev") -WorkingDirectory $BackendDir
Start-Process powershell -ArgumentList @("-NoExit", "-Command", "Set-Location -LiteralPath '$FrontendDir'; pnpm dev") -WorkingDirectory $FrontendDir
Write-Host "  ai-service: skipped (empty scaffold, nothing runnable yet)."

$backendUp = Wait-Healthy "Backend" "$ApiBase/health"
$frontendUp = Wait-Healthy "Frontend" "http://localhost:$FrontendPort/"

# --- Links -------------------------------------------------------------------
Write-Host ""
Write-Host "=============================================================="
Write-Host "  CodeAI is running"
Write-Host "=============================================================="
Write-Host "  Frontend (app UI)      http://localhost:$FrontendPort/"
Write-Host "  Backend health check   $ApiBase/health"
Write-Host ""
Write-Host "  API endpoints (need Clerk Bearer token, except health):"
Write-Host "    GET    $ApiBase/health"
Write-Host "    GET    $ApiBase/auth/me"
Write-Host "    GET    $ApiBase/projects"
Write-Host "    POST   $ApiBase/projects"
Write-Host "    GET    $ApiBase/repos"
Write-Host "    POST   $ApiBase/repos/connect"
Write-Host "    POST   $ApiBase/repos/:id/sync"
Write-Host "    GET    $ApiBase/repos/:id/snapshots/:sha/files"
Write-Host "    GET    $ApiBase/repos/:id/snapshots/:sha/diff"
Write-Host ""
if (-not $backendUp -or -not $frontendUp) {
  Write-Warning "One or more servers did not pass its health check. Read the errors in its window."
}
Write-Host "  To stop: close the two server windows (Ctrl+C inside each works too)."
Write-Host "=============================================================="
