# scripts/build.ps1 — сборка parser_nb-bet в .exe
# Использование: .\scripts\build.ps1 [-Debug] [-Clean]

param(
    [switch]$Debug,
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path $PSScriptRoot -Parent
$DistDir = Join-Path $ProjectRoot "dist"
$BuildDir = Join-Path $ProjectRoot "build"

Write-Host "=== parser_nb-bet Build ===" -ForegroundColor Cyan
Write-Host "Project root: $ProjectRoot"

# Очистка
if ($Clean) {
    Write-Host "Cleaning dist/ and build/ ..." -ForegroundColor Yellow
    if (Test-Path $DistDir) { Remove-Item $DistDir -Recurse -Force }
    if (Test-Path $BuildDir) { Remove-Item $BuildDir -Recurse -Force }
}

# Проверка venv
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv (Join-Path $ProjectRoot ".venv")
}

# Установка зависимостей
Write-Host "Installing dependencies..." -ForegroundColor Yellow
& $VenvPython -m pip install -q -r (Join-Path $ProjectRoot "requirements.txt")
& $VenvPython -m pip install -q pyinstaller

# Сборка
$MainScript = Join-Path $ProjectRoot "src\main.py"
$IconFile = Join-Path $ProjectRoot "assets\icon.ico"

$PyInstallerArgs = @(
    "--onefile",
    "--windowed",
    "--name", "parser_nb-bet",
    "--distpath", $DistDir,
    "--workpath", $BuildDir
)

if (Test-Path $IconFile) {
    $PyInstallerArgs += "--icon", $IconFile
}

if ($Debug) {
    $PyInstallerArgs += "--debug", "all"
    Write-Host "Building in DEBUG mode..." -ForegroundColor Yellow
} else {
    Write-Host "Building RELEASE..." -ForegroundColor Green
}

$PyInstallerArgs += $MainScript

Write-Host "Running PyInstaller..." -ForegroundColor Cyan
& $VenvPython -m PyInstaller @PyInstallerArgs

if ($LASTEXITCODE -eq 0) {
    $ExePath = Join-Path $DistDir "parser_nb-bet.exe"
    if (Test-Path $ExePath) {
        $Size = [math]::Round((Get-Item $ExePath).Length / 1MB, 2)
        Write-Host "SUCCESS: $ExePath ($Size MB)" -ForegroundColor Green
    }
} else {
    Write-Host "BUILD FAILED (exit code: $LASTEXITCODE)" -ForegroundColor Red
    exit $LASTEXITCODE
}
