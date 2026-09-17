param(
    [string]$OutputRoot = "",
    [switch]$Bootstrap,
    [switch]$SkipSmokeTest,
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $OutputRoot) {
    $OutputRoot = Join-Path $projectRoot ".artifacts\transportable"
}
$OutputRoot = [System.IO.Path]::GetFullPath($OutputRoot)
$buildVenv = Join-Path $projectRoot ".build-venv"
$python = Join-Path $buildVenv "Scripts\python.exe"

if ($Bootstrap) {
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if (-not $launcher) {
        throw "Python 3 is required to create the Windows distribution."
    }
    if (-not (Test-Path $python)) {
        & py -3 -m venv $buildVenv
    }
    & $python -m pip install --upgrade pip
    & $python -m pip install -r (Join-Path $projectRoot "requirements-build.txt")
}

if (-not (Test-Path $python)) {
    throw "Build environment missing. Run this script once with -Bootstrap."
}
& $python -c "import PyInstaller, PySide6, bs4" 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "Build dependencies are missing. Run this script with -Bootstrap."
}

$dist = Join-Path $OutputRoot "dist"
$work = Join-Path $OutputRoot "work"
$appFolder = Join-Path $dist "Character Sheet App"
$zipPath = Join-Path $OutputRoot "Character-Sheet-App-Portable.zip"
$smokeData = Join-Path $OutputRoot "smoke-data"

New-Item -ItemType Directory -Path $OutputRoot -Force | Out-Null
Remove-Item -LiteralPath $dist -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $zipPath -Force -ErrorAction SilentlyContinue

Push-Location $projectRoot
try {
    & $python -m PyInstaller `
        --noconfirm `
        --clean `
        --distpath $dist `
        --workpath $work `
        (Join-Path $PSScriptRoot "CharacterSheetApp.spec")
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}

Copy-Item -LiteralPath (Join-Path $PSScriptRoot "PORTABLE_README.txt") `
    -Destination (Join-Path $appFolder "README.txt") -Force

if (-not $SkipSmokeTest) {
    Remove-Item -LiteralPath $smokeData -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Path $smokeData -Force | Out-Null
    $oldDataOverride = $env:CHARACTER_SHEET_DATA_DIR
    try {
        $env:CHARACTER_SHEET_DATA_DIR = $smokeData
        & (Join-Path $appFolder "Character Sheet App.exe") --smoke-test
        if ($LASTEXITCODE -ne 0) {
            throw "The packaged application smoke test failed with exit code $LASTEXITCODE."
        }
    }
    finally {
        $env:CHARACTER_SHEET_DATA_DIR = $oldDataOverride
        Remove-Item -LiteralPath $smokeData -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Compress-Archive -Path $appFolder -DestinationPath $zipPath -CompressionLevel Optimal

if (-not $SkipInstaller) {
    $isccCandidates = @(
        (Get-Command ISCC.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -ErrorAction SilentlyContinue),
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
    ) | Where-Object { $_ -and (Test-Path $_) }
    $iscc = $isccCandidates | Select-Object -First 1
    if ($iscc) {
        & $iscc `
            "/DSourceDir=$appFolder" `
            "/DOutputDir=$OutputRoot" `
            (Join-Path $PSScriptRoot "CharacterSheetApp.iss")
        if ($LASTEXITCODE -ne 0) {
            throw "Inno Setup failed with exit code $LASTEXITCODE."
        }
    }
    else {
        Write-Warning "Inno Setup 6 was not found; portable ZIP created, installer skipped."
    }
}

Write-Host "Transportable build ready in: $OutputRoot"
Write-Host "Portable ZIP: $zipPath"

