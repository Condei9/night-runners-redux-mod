param(
    [string]$Python = "python"
)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Test-Path ".venv")) {
    & $Python -m venv .venv
}
$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
& $py -m pip install --upgrade pip
& $py -m pip install -r requirements.txt pyinstaller==6.20.0
& $py -m PyInstaller --noconfirm --clean --onefile --windowed --name "NIGHT-RUNNERS REDUX Patcher" --add-data "patches;patches" run_patcher.py
Write-Host "Built dist\NIGHT-RUNNERS REDUX Patcher.exe"
