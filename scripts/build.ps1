# scripts/build.ps1 — сборка parser_nb-bet в .exe через dotnet publish
# Использование: .\scripts\build.ps1 [-Configuration Debug|Release] [-Clean]
#
# Требования: .NET 8 SDK (https://dotnet.microsoft.com/download/dotnet/8.0)

param(
    [ValidateSet("Debug","Release")]
    [string]$Configuration = "Release",
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$ProjectRoot  = Split-Path $PSScriptRoot -Parent
$ProjectFile  = Join-Path $ProjectRoot "src\ParserNbBet\ParserNbBet.csproj"
$DistDir      = Join-Path $ProjectRoot "dist"

Write-Host "=== parser_nb-bet Build ===" -ForegroundColor Cyan
Write-Host "Configuration : $Configuration"
Write-Host "Project       : $ProjectFile"
Write-Host "Output        : $DistDir"

if ($Clean -and (Test-Path $DistDir)) {
    Write-Host "Cleaning dist/ ..." -ForegroundColor Yellow
    Remove-Item $DistDir -Recurse -Force
}

# dotnet publish: self-contained single-file exe for win-x64
$publishArgs = @(
    "publish", $ProjectFile,
    "--configuration", $Configuration,
    "--runtime",       "win-x64",
    "--self-contained", "true",
    "-p:PublishSingleFile=true",
    "-p:IncludeNativeLibrariesForSelfExtract=true",
    "--output", $DistDir
)

Write-Host "Running: dotnet $($publishArgs -join ' ')" -ForegroundColor Gray
dotnet @publishArgs

if ($LASTEXITCODE -ne 0) {
    Write-Host "BUILD FAILED (exit code: $LASTEXITCODE)" -ForegroundColor Red
    exit $LASTEXITCODE
}

$ExePath = Join-Path $DistDir "parser_nb-bet.exe"
if (Test-Path $ExePath) {
    $SizeMB = [math]::Round((Get-Item $ExePath).Length / 1MB, 1)
    Write-Host ""
    Write-Host "SUCCESS: $ExePath ($SizeMB MB)" -ForegroundColor Green
} else {
    Write-Host "WARNING: exe not found at expected path" -ForegroundColor Yellow
}
