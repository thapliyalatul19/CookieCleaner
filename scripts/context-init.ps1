#!/usr/bin/env pwsh
# Cookie Cleaner - Context Architecture Bootstrap (PowerShell)

Write-Host "🚀 Bootstrapping Context Architecture for Cookie Cleaner..." -ForegroundColor Cyan

# Memory Bank Check
Write-Host "📝 Checking Memory Bank files..." -ForegroundColor Yellow
$memoryFiles = Get-ChildItem -Path ".context\*.md" -ErrorAction SilentlyContinue
if ($memoryFiles) {
    foreach ($file in $memoryFiles) {
        Write-Host "✅ $($file.Name) exists." -ForegroundColor Green
    }
} else {
    Write-Host "⚠️  Memory Bank files not found." -ForegroundColor Yellow
}

# Validation Script Check
if (Test-Path "scripts\validate-context.ps1") {
    Write-Host "✅ Validation script exists." -ForegroundColor Green
}

# Pre-Commit Hook Check
if (Test-Path ".git\hooks\pre-commit") {
    Write-Host "✅ Pre-commit hook installed." -ForegroundColor Green
}

Write-Host ""
Write-Host "🎉 Bootstrap verification complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Cyan
Write-Host "  1. Review CLAUDE.md (the constitution)"
Write-Host "  2. Read Memory Bank: Get-Content .context\*.md"
Write-Host "  3. Start Phase 1 implementation"
