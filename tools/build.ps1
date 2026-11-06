#!/usr/bin/env pwsh
<#
.SYNOPSIS
Build one viewer as a one-folder Windows app (PySide6 + PyInstaller). One-folder starts in ~0.3 s.
.EXAMPLE
.\tools\build.ps1 -App pptx
#>
param([Parameter(Mandatory)][ValidateSet("pptx", "csv")][string]$App)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))

$names = @{ pptx = "PPTX Viewer"; csv = "CSV Viewer" }
if (-not (Test-Path ".venv")) { python -m venv .venv }
$py = ".\.venv\Scripts\python.exe"
& $py -m pip install -q -e ".[dev]"
& $py "apps\$App\resources\generate_icon.py"

# frozen exes can't run package-relative imports from a script, so generate a tiny launcher per app
$launcher = "build\launch_$App.py"
New-Item -ItemType Directory -Force build | Out-Null
"from apps.$App.main import main`nmain()" | Set-Content $launcher -Encoding utf8

& $py -m PyInstaller --noconfirm --clean --onedir --windowed --noupx `
    --name $names[$App] `
    --icon "apps\$App\resources\app.ico" `
    --add-data "apps\$App\resources;resources" `
    --paths core --paths . `
    --distpath app --workpath build\work `
    --exclude-module PySide6.QtNetwork --exclude-module PySide6.QtQml --exclude-module PySide6.QtQuick `
    --exclude-module tkinter --exclude-module unittest `
    $launcher
if ($LASTEXITCODE -ne 0) { Write-Host "[FAIL] build failed" -ForegroundColor Red; exit 1 }
Write-Host "[OK] app\$($names[$App])\$($names[$App]).exe" -ForegroundColor Green
