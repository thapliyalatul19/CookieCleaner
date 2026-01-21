#!/usr/bin/env pwsh
# Cookie Cleaner - Context Validation Script (PowerShell)
# Enforces Memory Bank integrity and Supervisor Mode rules

$ErrorActionPreference = "Stop"

# 1. Ensure Memory Bank files are not empty
Write-Host "Validating Memory Bank files..." -ForegroundColor Yellow

$memoryFiles = @(
    ".context\projectbrief.md",
    ".context\productContext.md",
    ".context\systemPatterns.md",
    ".context\activeContext.md"
)

foreach ($file in $memoryFiles) {
    if (-not (Test-Path $file)) {
        Write-Host "❌ Validation Error: $file is missing." -ForegroundColor Red
        exit 1
    }
    
    $content = Get-Content $file -Raw
    if ([string]::IsNullOrWhiteSpace($content)) {
        Write-Host "❌ Validation Error: $file is empty." -ForegroundColor Red
        Write-Host "   Memory Bank files must contain content." -ForegroundColor Red
        exit 1
    }
}

# 2. Supervisor-mode guard
$supervisorMode = $env:SUPERVISOR_MODE
if ($supervisorMode -eq "1") {
    Write-Host "Checking Supervisor Mode constraints..." -ForegroundColor Yellow
    
    $stagedFiles = git diff --cached --name-only | Out-String
    $prohibitedFiles = $stagedFiles -split "`n" | Where-Object { 
        $_ -match "^(src/|lib/|app/)" 
    }
    
    if ($prohibitedFiles) {
        Write-Host "❌ SUPERVISOR VIOLATION: source file changes staged while SUPERVISOR_MODE=1." -ForegroundColor Red
        Write-Host "   Supervisor must emit patch/diff and instruct Worker to apply." -ForegroundColor Red
        Write-Host "   Blocked files:" -ForegroundColor Red
        $prohibitedFiles | ForEach-Object { Write-Host "     $_" -ForegroundColor Red }
        exit 1
    }
    
    Write-Host "✅ Supervisor Mode: No prohibited changes detected." -ForegroundColor Green
}

Write-Host "✅ Context Validated." -ForegroundColor Green
exit 0
