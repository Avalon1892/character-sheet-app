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

# PyInstaller searches PATH for dependent DLLs. Do not bundle unrelated toolchains.
$basePython = & $python -I -c "import sys; print(sys.base_prefix)"
if ($LASTEXITCODE -ne 0) {
    throw "Could not resolve the build environment's base Python."
}
$buildPath = (@(
    (Join-Path $buildVenv "Scripts"),
    (Join-Path $buildVenv "Lib\site-packages\PySide6"),
    $basePython,
    (Join-Path $basePython "DLLs"),
    (Join-Path $env:SystemRoot "System32"),
    $env:SystemRoot
) | Where-Object { Test-Path -LiteralPath $_ -PathType Container }) -join [IO.Path]::PathSeparator

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
$oldPath = $env:PATH
try {
    $env:PATH = $buildPath
    & $python -I -m PyInstaller `
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
    $env:PATH = $oldPath
    Pop-Location
}

Copy-Item -LiteralPath (Join-Path $PSScriptRoot "PORTABLE_README.txt") `
    -Destination (Join-Path $appFolder "README.txt") -Force

if (-not $SkipSmokeTest) {
    Remove-Item -LiteralPath $smokeData -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Path $smokeData -Force | Out-Null
    $oldDataOverride = $env:CHARACTER_SHEET_DATA_DIR
    $oldPath = $env:PATH
    try {
        $env:PATH = $buildPath
        $env:CHARACTER_SHEET_DATA_DIR = $smokeData
        $smokeProcess = Start-Process -FilePath (Join-Path $appFolder "Character Sheet App.exe") `
            -ArgumentList "--smoke-test" -WindowStyle Hidden -PassThru -Wait
        if ($smokeProcess.ExitCode -ne 0) {
            throw "The packaged application smoke test failed with exit code $($smokeProcess.ExitCode)."
        }
    }
    finally {
        $env:PATH = $oldPath
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
