$ErrorActionPreference = "Stop"

Write-Host "Building SmartDSS executable..." -ForegroundColor Cyan

# Optional: create icon if missing
if (-not (Test-Path "assets\app_icon.ico")) {
  Write-Host "Icon missing; generating assets\app_icon.ico" -ForegroundColor Yellow
  python .\scripts\build\create_icon.py
}

# Ensure PyInstaller is available
python -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
  Write-Host "PyInstaller not found. Installing from requirements.txt..." -ForegroundColor Yellow
  pip install -r .\requirements.txt
}

python -m PyInstaller .\dss.spec

Write-Host ""
Write-Host "Build complete." -ForegroundColor Green
Write-Host "Your executable is in: dist\SmartDSS.exe" -ForegroundColor Green

