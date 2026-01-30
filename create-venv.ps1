# Create Tidypy Virtual Environment
$ProjectRoot = "C:\Users\Dev\Documents\APPS\Tidypy-Chess-Rep-Builder"

Write-Host "Creating virtual environment..." -ForegroundColor Cyan

# Create project directory if needed
if (!(Test-Path $ProjectRoot)) {
    New-Item -ItemType Directory -Path $ProjectRoot -Force | Out-Null
}

Set-Location $ProjectRoot

# Create venv
py -m venv venv

Write-Host "Activating venv..." -ForegroundColor Cyan
& "$ProjectRoot\venv\Scripts\Activate.ps1"

Write-Host "Installing dependencies..." -ForegroundColor Cyan
pip install --upgrade pip
pip install python-chess PyQt6 qt-material pyinstaller

Write-Host ""
Write-Host "Done! Venv created at: $ProjectRoot\venv" -ForegroundColor Green
Write-Host ""
Write-Host "To activate later, run:" -ForegroundColor Yellow
Write-Host "  cd $ProjectRoot" -ForegroundColor White
Write-Host "  .\venv\Scripts\Activate.ps1" -ForegroundColor White