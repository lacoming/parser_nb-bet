# scripts/build.ps1 — сборка parser_nb-bet в .exe (PyInstaller + UPX)
# Использование: .\scripts\build.ps1 [-Debug] [-Clean] [-NoUPX]

param(
    [switch]$Debug,
    [switch]$Clean,
    [switch]$NoUPX
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path $PSScriptRoot -Parent
$DistDir = Join-Path $ProjectRoot "dist"
$BuildDir = Join-Path $ProjectRoot "build"
$DataDir = Join-Path $ProjectRoot "assets\data"

Write-Host "=== parser_nb-bet Build ===" -ForegroundColor Cyan
Write-Host "Project root: $ProjectRoot"

# Очистка
if ($Clean) {
    Write-Host "Cleaning dist/ and build/ ..." -ForegroundColor Yellow
    if (Test-Path $DistDir) { Remove-Item $DistDir -Recurse -Force }
    if (Test-Path $BuildDir) { Remove-Item $BuildDir -Recurse -Force }
}

# Проверка Python
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
    "--name", "parser_nb-bet",
    "--distpath", $DistDir,
    "--workpath", $BuildDir,
    "--add-data", "$DataDir;assets/data"
)

# Exclude unused modules to reduce size
$Excludes = @(
    "matplotlib", "numpy", "scipy", "pandas", "PIL", "pillow",
    "tkinter.test", "unittest", "email", "html.parser",
    "pydoc", "doctest", "argparse", "difflib",
    "setuptools", "pkg_resources", "wheel"
)
foreach ($exc in $Excludes) {
    $PyInstallerArgs += "--exclude-module", $exc
}

if (Test-Path $IconFile) {
    $PyInstallerArgs += "--icon", $IconFile
}

if (-not $NoUPX) {
    # UPX compression (if available in PATH)
    $upx = Get-Command upx -ErrorAction SilentlyContinue
    if ($upx) {
        $PyInstallerArgs += "--upx-dir", (Split-Path $upx.Source -Parent)
        Write-Host "UPX found: $($upx.Source)" -ForegroundColor Green
    } else {
        Write-Host "UPX not found — building without compression" -ForegroundColor Yellow
    }
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
        Write-Host ""
        Write-Host "SUCCESS: $ExePath" -ForegroundColor Green
        Write-Host "Size: $Size MB" -ForegroundColor $(if ($Size -lt 10) { "Green" } else { "Red" })
        if ($Size -ge 10) {
            Write-Host "WARNING: exe exceeds 10 MB target!" -ForegroundColor Red
        }
    }
} else {
    Write-Host "BUILD FAILED (exit code: $LASTEXITCODE)" -ForegroundColor Red
    exit $LASTEXITCODE
}
