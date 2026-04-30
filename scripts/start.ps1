[CmdletBinding()]
param(
  [switch]$SkipInstall,
  [switch]$SkipValidation,
  [switch]$NoRun
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Info($m) { Write-Host "[INFO] $m" -ForegroundColor Cyan }
function Warn($m) { Write-Host "[WARN] $m" -ForegroundColor Yellow }
function Fail($m) { Write-Host "[ERROR] $m" -ForegroundColor Red }

function Require-Command([string]$Name, [string]$InstallHint) {
  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
    throw "Missing required command '$Name'. $InstallHint"
  }
}

function Ensure-Directory([string]$Path) {
  if (-not (Test-Path $Path)) {
    New-Item -ItemType Directory -Path $Path | Out-Null
    Info "Created directory: $Path"
  }
}

function Install-Dependencies {
  Info "Installing pinned dependencies"
  if (Test-Path "requirements.txt") {
    Require-Command "python" "Install Python 3.11+ and add it to PATH."
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
  } else {
    Warn "requirements.txt not found. Skipping Python dependency install."
  }

  if (Test-Path "package-lock.json") {
    Require-Command "npm" "Install Node.js 20 LTS and npm."
    npm ci
  } elseif (Test-Path "package.json") {
    Require-Command "npm" "Install Node.js 20 LTS and npm."
    npm install
  } else {
    Warn "No package.json found. Skipping Node dependency install."
  }
}

function Initialize-Storage {
  Info "Preparing required directories"
  $dirs = @(
    "jobs",
    "logs",
    "storage",
    "samples",
    "storage/output",
    "storage/output/json",
    "storage/output/text",
    "storage/output/pdf"
  )

  foreach ($d in $dirs) { Ensure-Directory $d }

  if (-not (Test-Path "storage/app.db")) {
    New-Item -ItemType File -Path "storage/app.db" | Out-Null
    Info "Created storage/app.db"
  }
}

function Run-Sqlite-Migrations {
  Info "Initializing / migrating SQLite"
  if (Test-Path "migrations") {
    if (Get-Command "alembic" -ErrorAction SilentlyContinue) {
      & alembic upgrade head
      return
    }
    Warn "migrations/ found, but alembic isn't installed. Install backend deps and retry."
    return
  }

  if (Test-Path "schema.sql") {
    if (Get-Command "sqlite3" -ErrorAction SilentlyContinue) {
      & sqlite3 "storage/app.db" ".read schema.sql"
      return
    }
    Warn "schema.sql found, but sqlite3 CLI is unavailable. Falling back to app-managed schema initialization."
    return
  }

  Warn "No migrations/ or schema.sql found; assuming app initializes schema at runtime."
}

function Validate-Runtime {
  Info "Validating runtime and optional OCR/PDF dependencies"

  try { Require-Command "python" "Install Python 3.11+ and add it to PATH."; python --version }
  catch { Fail $_; throw }

  if (Get-Command "node" -ErrorAction SilentlyContinue) { node --version }
  else { Warn "Node.js not found. UI may not start unless prebuilt artifacts exist." }

  if (Get-Command "tesseract" -ErrorAction SilentlyContinue) {
    tesseract --version | Select-Object -First 1
  } else {
    Warn "Tesseract OCR not found. OCR features may be disabled. Install from https://github.com/tesseract-ocr/tesseract and restart."
  }

  if (Get-Command "pdftoppm" -ErrorAction SilentlyContinue) {
    Info "Found pdftoppm (Poppler)."
  } else {
    Warn "Poppler tools (pdftoppm) not found. PDF rasterization may fail. Install Poppler for Windows and add /bin to PATH."
  }

  if (Get-Command "gswin64c" -ErrorAction SilentlyContinue) {
    Info "Found Ghostscript."
  } else {
    Warn "Ghostscript not found. Some PDF workflows may be limited. Install Ghostscript if needed."
  }
}

function Start-Services {
  $backendCmd = if ($env:BACKEND_START_CMD) { $env:BACKEND_START_CMD } else { "python -m uvicorn app.main:app --reload --port 8000" }
  $uiCmd = if ($env:UI_START_CMD) { $env:UI_START_CMD } else { "npm run dev" }

  Info "Starting backend in separate window"
  Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -Command cd '$PWD'; $backendCmd"

  Info "Starting UI in separate window"
  Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -Command cd '$PWD'; $uiCmd"

  Info "Backend + UI launched."
}

try {
  if (-not $SkipInstall) { Install-Dependencies }
  Initialize-Storage
  Run-Sqlite-Migrations
  if (-not $SkipValidation) { Validate-Runtime }
  if (-not $NoRun) { Start-Services }
  Info "Startup workflow completed."
}
catch {
  Fail $_
  Warn "Fallback guidance:"
  Warn "1) Re-run with -SkipInstall if offline; 2) set BACKEND_START_CMD/UI_START_CMD for custom commands; 3) install OCR/PDF tools if features are unavailable."
  exit 1
}
