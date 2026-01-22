<#
.SYNOPSIS
    Build Cookie Cleaner standalone executable.

.DESCRIPTION
    This script builds the Cookie Cleaner application into a standalone
    Windows executable using PyInstaller. The output is a single .exe file
    that can run without Python installed.

.EXAMPLE
    .\build.ps1
    # Builds the application with default settings

.EXAMPLE
    .\build.ps1 -Clean
    # Performs a clean build, removing previous build artifacts

.NOTES
    Requirements:
    - Python 3.10+
    - Virtual environment with dependencies installed
    - PyInstaller installed in the virtual environment
#>

param(
    [switch]$Clean,
    [switch]$Debug,
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"

# Configuration
$ProjectRoot = $PSScriptRoot
$VenvPath = Join-Path $ProjectRoot ".venv"
$DistPath = Join-Path $ProjectRoot "dist"
$BuildPath = Join-Path $ProjectRoot "build"
$SpecFile = Join-Path $ProjectRoot "cookie_cleaner.spec"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Cookie Cleaner Build Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check for virtual environment
if (-not (Test-Path $VenvPath)) {
    Write-Host "Error: Virtual environment not found at $VenvPath" -ForegroundColor Red
    Write-Host "Please create a virtual environment first:" -ForegroundColor Yellow
    Write-Host "  python -m venv .venv" -ForegroundColor Yellow
    Write-Host "  .\.venv\Scripts\Activate.ps1" -ForegroundColor Yellow
    Write-Host "  pip install -r requirements.txt" -ForegroundColor Yellow
    exit 1
}

# Activate virtual environment
Write-Host "[1/5] Activating virtual environment..." -ForegroundColor Green
$ActivateScript = Join-Path $VenvPath "Scripts\Activate.ps1"
. $ActivateScript

# Verify Python and pip
Write-Host "[2/5] Verifying environment..." -ForegroundColor Green
$PythonVersion = python --version
Write-Host "  Python: $PythonVersion" -ForegroundColor Gray

# Install/update PyInstaller if needed
Write-Host "[3/5] Ensuring PyInstaller is installed..." -ForegroundColor Green
pip install pyinstaller --quiet --upgrade
$PyInstallerVersion = pyinstaller --version
Write-Host "  PyInstaller: $PyInstallerVersion" -ForegroundColor Gray

# Run tests unless skipped
if (-not $SkipTests) {
    Write-Host "[4/5] Running tests..." -ForegroundColor Green
    try {
        pytest tests/ -v --tb=short
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Tests failed! Aborting build." -ForegroundColor Red
            exit 1
        }
        Write-Host "  All tests passed!" -ForegroundColor Green
    }
    catch {
        Write-Host "Warning: Could not run tests. Continuing with build..." -ForegroundColor Yellow
    }
}
else {
    Write-Host "[4/5] Skipping tests (--SkipTests flag)" -ForegroundColor Yellow
}

# Clean previous builds if requested
if ($Clean) {
    Write-Host "[4.5/5] Cleaning previous build artifacts..." -ForegroundColor Green
    if (Test-Path $DistPath) {
        Remove-Item -Recurse -Force $DistPath
    }
    if (Test-Path $BuildPath) {
        Remove-Item -Recurse -Force $BuildPath
    }
}

# Build the executable
Write-Host "[5/5] Building executable..." -ForegroundColor Green

$PyInstallerArgs = @(
    $SpecFile
    "--noconfirm"
)

if ($Clean) {
    $PyInstallerArgs += "--clean"
}

if ($Debug) {
    Write-Host "  Debug mode enabled" -ForegroundColor Yellow
    # For debug builds, we might want to keep the console
    # This would require modifying the spec file or using command line args
}

pyinstaller @PyInstallerArgs

if ($LASTEXITCODE -ne 0) {
    Write-Host "Build failed!" -ForegroundColor Red
    exit 1
}

# Verify output
$ExePath = Join-Path $DistPath "CookieCleaner.exe"
if (Test-Path $ExePath) {
    $FileInfo = Get-Item $ExePath
    $SizeMB = [math]::Round($FileInfo.Length / 1MB, 2)

    Write-Host ""
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  Build Successful!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Output: $ExePath" -ForegroundColor White
    Write-Host "Size: $SizeMB MB" -ForegroundColor White
    Write-Host ""
    Write-Host "To run the application:" -ForegroundColor Cyan
    Write-Host "  .\dist\CookieCleaner.exe" -ForegroundColor White
}
else {
    Write-Host "Error: Expected output file not found!" -ForegroundColor Red
    exit 1
}
