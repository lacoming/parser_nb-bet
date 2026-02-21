# scripts/build.ps1 — сборка parser_nb-bet в .exe через dotnet publish
#
# Использование:
#   .\scripts\build.ps1                        # Release, self-contained (~60-80 MB)
#   .\scripts\build.ps1 -Configuration Debug   # Debug build
#   .\scripts\build.ps1 -Clean                 # Очистить dist/ перед сборкой
#   .\scripts\build.ps1 -FrameworkDependent     # Маленький .exe (~5-10 MB), требует .NET 8 Runtime
#   .\scripts\build.ps1 -Trim                  # Trimming (экспериментально, -30-50% размер)
#
# Требования: .NET 8 SDK (https://dotnet.microsoft.com/download/dotnet/8.0)
#
# Стратегия (см. ARCHITECTURE.md):
#   - По умолчанию: self-contained single-file + ReadyToRun. Заказчику не нужен .NET Runtime.
#   - Trimming отключён по умолчанию (WinForms/ClosedXML/SQLite = reflection-heavy).
#   - Framework-dependent — только для разработки/тестирования.

param(
    [ValidateSet("Debug","Release")]
    [string]$Configuration = "Release",
    [switch]$Clean,
    [switch]$FrameworkDependent,
    [switch]$Trim
)

$ErrorActionPreference = "Stop"
$ProjectRoot  = Split-Path $PSScriptRoot -Parent
$ProjectFile  = Join-Path $ProjectRoot "src\ParserNbBet\ParserNbBet.csproj"
$DistDir      = Join-Path $ProjectRoot "dist"

# Preflight: check dotnet SDK
$dotnetVersion = dotnet --version 2>$null
if (-not $dotnetVersion) {
    Write-Host "ERROR: dotnet SDK not found. Install .NET 8 SDK:" -ForegroundColor Red
    Write-Host "  https://dotnet.microsoft.com/download/dotnet/8.0" -ForegroundColor Yellow
    exit 1
}

Write-Host "=== parser_nb-bet Build ===" -ForegroundColor Cyan
Write-Host "dotnet SDK    : $dotnetVersion"
Write-Host "Configuration : $Configuration"
Write-Host "Self-contained: $(-not $FrameworkDependent)"
Write-Host "Trimming      : $Trim"
Write-Host "Project       : $ProjectFile"
Write-Host "Output        : $DistDir"
Write-Host ""

if ($Clean -and (Test-Path $DistDir)) {
    Write-Host "Cleaning dist/ ..." -ForegroundColor Yellow
    Remove-Item $DistDir -Recurse -Force
}

# Build publish arguments
$publishArgs = @(
    "publish", $ProjectFile,
    "--configuration", $Configuration,
    "--runtime", "win-x64",
    "-p:PublishSingleFile=true",
    "-p:IncludeNativeLibrariesForSelfExtract=true",
    "-p:PublishReadyToRun=true",
    "--output", $DistDir
)

if ($FrameworkDependent) {
    $publishArgs += "--self-contained", "false"
} else {
    $publishArgs += "--self-contained", "true"
}

if ($Trim) {
    Write-Host "WARNING: Trimming enabled. Test thoroughly — WinForms/reflection may break." -ForegroundColor Yellow
    $publishArgs += "-p:PublishTrimmed=true"
    $publishArgs += "-p:TrimMode=partial"
}

Write-Host "Running: dotnet $($publishArgs -join ' ')" -ForegroundColor Gray
Write-Host ""
dotnet @publishArgs

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "BUILD FAILED (exit code: $LASTEXITCODE)" -ForegroundColor Red
    exit $LASTEXITCODE
}

# Report result
$ExePath = Join-Path $DistDir "parser_nb-bet.exe"
if (Test-Path $ExePath) {
    $SizeBytes = (Get-Item $ExePath).Length
    $SizeMB = [math]::Round($SizeBytes / 1MB, 1)
    Write-Host ""
    Write-Host "SUCCESS: $ExePath ($SizeMB MB)" -ForegroundColor Green

    if ($SizeMB -gt 100) {
        Write-Host "NOTE: exe is large. Consider -FrameworkDependent for dev builds." -ForegroundColor Yellow
    }
} else {
    Write-Host "WARNING: exe not found at expected path ($ExePath)" -ForegroundColor Yellow
}
