# Build the GetifyCo Listing Portal app on Windows -> dist\getifyco-listing-portal\getifyco-listing-portal.exe
# Run from the desktop\ directory:  powershell -ExecutionPolicy Bypass -File build.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$py = if ($env:PYTHON) { $env:PYTHON } else { "python" }

Write-Host "==> Installing desktop build deps"
& $py -m pip install --upgrade pip
& $py -m pip install -r requirements-desktop.txt

Write-Host "==> Cleaning previous build"
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue

Write-Host "==> Running PyInstaller"
& $py -m PyInstaller --noconfirm --clean Getify.spec

Write-Host "==> Done. Output in: desktop\dist\getifyco-listing-portal\"
Get-ChildItem dist
