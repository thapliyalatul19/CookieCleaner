<#
.SYNOPSIS
    Full installer build script for Cookie Cleaner.

.DESCRIPTION
    This script performs a complete build and packaging of Cookie Cleaner:
    1. Validates environment
    2. Runs full test suite
    3. Builds standalone executable
    4. Creates distribution package

.EXAMPLE
    .\scripts\build_installer.ps1
    # Full build with all checks

.EXAMPLE
    .\scripts\build_installer.ps1 -SkipTests -Verbose
    # Skip tests, verbose output

.NOTES
    This script should be run from the project root directory.
    Requires: Python 3.10+, Git, PyInstaller
#>

[CmdletBinding()]
param(
    [switch]$SkipTests,
    [switch]$SkipLint,
    [switch]$Clean,
    [string]$Version = "1.0.0"
)

$ErrorActionPreference = "Stop"

# Configuration
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvPath = Join-Path $ProjectRoot ".venv"
$DistPath = Join-Path $ProjectRoot "dist"
$BuildPath = Join-Path $ProjectRoot "build"
$SpecFile = Join-Path $ProjectRoot "cookie_cleaner.spec"

function Write-Step {
    param([string]$Message, [int]$Step, [int]$Total)
    Write-Host ""
    Write-Host "[$Step/$Total] $Message" -ForegroundColor Cyan
    Write-Host ("-" * 50) -ForegroundColor DarkGray
}

function Write-Success {
    param([string]$Message)
    Write-Host "  [OK] $Message" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "  [WARN] $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "  [ERROR] $Message" -ForegroundColor Red
}

# Banner
Write-Host ""
Write-Host "================================================" -ForegroundColor Magenta
Write-Host "  Cookie Cleaner - Full Build Script" -ForegroundColor Magenta
Write-Host "  Version: $Version" -ForegroundColor Magenta
Write-Host "================================================" -ForegroundColor Magenta
Write-Host ""

$TotalSteps = 6
$CurrentStep = 0

# Step 1: Environment Validation
$CurrentStep++
Write-Step "Validating environment" $CurrentStep $TotalSteps

# Check Python
try {
    $PythonVersion = python --version 2>&1
    Write-Success "Python found: $PythonVersion"
}
catch {
    Write-Error "Python not found in PATH"
    exit 1
}

# Check virtual environment
if (-not (Test-Path $VenvPath)) {
    Write-Error "Virtual environment not found at: $VenvPath"
    Write-Host ""
    Write-Host "  To create the virtual environment:" -ForegroundColor Yellow
    Write-Host "    python -m venv .venv" -ForegroundColor White
    Write-Host "    .\.venv\Scripts\Activate.ps1" -ForegroundColor White
    Write-Host "    pip install -r requirements.txt" -ForegroundColor White
    exit 1
}
Write-Success "Virtual environment found"

# Activate virtual environment
$ActivateScript = Join-Path $VenvPath "Scripts\Activate.ps1"
. $ActivateScript
Write-Success "Virtual environment activated"

# Check Git
try {
    $GitVersion = git --version 2>&1
    Write-Success "Git found: $GitVersion"

    # Get current commit
    $GitCommit = git rev-parse --short HEAD 2>&1
    Write-Verbose "  Git commit: $GitCommit"
}
catch {
    Write-Warning "Git not found - version info will be limited"
}

# Step 2: Install/Verify Dependencies
$CurrentStep++
Write-Step "Verifying dependencies" $CurrentStep $TotalSteps

pip install --quiet --upgrade pip
Write-Success "pip updated"

pip install --quiet -r requirements.txt
Write-Success "Dependencies installed"

pip install --quiet pyinstaller
$PyInstallerVersion = pyinstaller --version
Write-Success "PyInstaller ready: $PyInstallerVersion"

# Step 3: Run Linting (Optional)
$CurrentStep++
if ($SkipLint) {
    Write-Step "Skipping lint checks (--SkipLint)" $CurrentStep $TotalSteps
}
else {
    Write-Step "Running lint checks" $CurrentStep $TotalSteps

    try {
        # Check if flake8 is available
        pip install --quiet flake8

        Write-Host "  Running flake8..." -ForegroundColor Gray
        $LintOutput = flake8 src/ --count --select=E9,F63,F7,F82 --show-source --statistics 2>&1

        if ($LASTEXITCODE -eq 0) {
            Write-Success "No critical lint errors"
        }
        else {
            Write-Warning "Lint issues found (non-blocking)"
            Write-Verbose $LintOutput
        }
    }
    catch {
        Write-Warning "Lint check skipped (flake8 not available)"
    }
}

# Step 4: Run Tests
$CurrentStep++
if ($SkipTests) {
    Write-Step "Skipping tests (--SkipTests)" $CurrentStep $TotalSteps
}
else {
    Write-Step "Running test suite" $CurrentStep $TotalSteps

    Write-Host "  Running pytest..." -ForegroundColor Gray

    pytest tests/ -v --tb=short -q

    if ($LASTEXITCODE -ne 0) {
        Write-Error "Tests failed! Build aborted."
        exit 1
    }

    Write-Success "All tests passed"
}

# Step 5: Build Executable
$CurrentStep++
Write-Step "Building executable" $CurrentStep $TotalSteps

# Clean if requested
if ($Clean) {
    Write-Host "  Cleaning previous builds..." -ForegroundColor Gray
    if (Test-Path $DistPath) { Remove-Item -Recurse -Force $DistPath }
    if (Test-Path $BuildPath) { Remove-Item -Recurse -Force $BuildPath }
    Write-Success "Previous builds cleaned"
}

Write-Host "  Running PyInstaller..." -ForegroundColor Gray

$PyInstallerArgs = @(
    $SpecFile
    "--noconfirm"
)

if ($Clean) {
    $PyInstallerArgs += "--clean"
}

pyinstaller @PyInstallerArgs

if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller build failed!"
    exit 1
}

Write-Success "Build completed"

# Step 6: Verify Output
$CurrentStep++
Write-Step "Verifying build output" $CurrentStep $TotalSteps

$ExePath = Join-Path $DistPath "CookieCleaner.exe"

if (-not (Test-Path $ExePath)) {
    Write-Error "Expected output not found: $ExePath"
    exit 1
}

$FileInfo = Get-Item $ExePath
$SizeMB = [math]::Round($FileInfo.Length / 1MB, 2)
$ModTime = $FileInfo.LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss")

Write-Success "Executable created"
Write-Host ""
Write-Host "  File: $ExePath" -ForegroundColor White
Write-Host "  Size: $SizeMB MB" -ForegroundColor White
Write-Host "  Built: $ModTime" -ForegroundColor White

# Create version info file
$VersionInfo = @{
    version = $Version
    build_date = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    git_commit = $GitCommit
    python_version = $PythonVersion
    pyinstaller_version = $PyInstallerVersion
    file_size_bytes = $FileInfo.Length
}

$VersionInfoPath = Join-Path $DistPath "version.json"
$VersionInfo | ConvertTo-Json | Out-File -FilePath $VersionInfoPath -Encoding utf8

Write-Success "Version info saved to: $VersionInfoPath"

# Final Summary
Write-Host ""
Write-Host "================================================" -ForegroundColor Green
Write-Host "  BUILD SUCCESSFUL" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Executable: .\dist\CookieCleaner.exe" -ForegroundColor White
Write-Host "  Size: $SizeMB MB" -ForegroundColor White
Write-Host "  Version: $Version" -ForegroundColor White
Write-Host ""
Write-Host "  To test the build:" -ForegroundColor Cyan
Write-Host "    .\dist\CookieCleaner.exe" -ForegroundColor White
Write-Host ""
