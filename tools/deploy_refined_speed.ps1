$ErrorActionPreference = 'Stop'
$source = Split-Path -Parent $PSScriptRoot
$destination = 'C:\Users\Georg\Desktop\Character Sheet App'
$backup = Join-Path $destination ('.backups\refined-speed-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
$files = @(
    'app\presentation_storage.py',
    'app\class_feature_rules.py',
    'app\ui\sheet_types.py',
    'app\ui\main_window.py',
    'app\ui\customization.py',
    'app\ui\refined\components.py',
    'app\ui\refined\sheet.py',
    'tests\test_refined_performance.py',
    'tests\test_refined_sheet.py',
    'tests\test_sheet_types_ui.py',
    'tests\test_building_blocks_ui.py',
    'tools\check_refined_responsiveness.py'
)
New-Item -ItemType Directory -Path $backup -Force | Out-Null
foreach ($relative in $files) {
    $installed = Join-Path $destination $relative
    if (Test-Path -LiteralPath $installed) {
        $saved = Join-Path $backup $relative
        New-Item -ItemType Directory -Path (Split-Path -Parent $saved) -Force | Out-Null
        Copy-Item -LiteralPath $installed -Destination $saved
    }
}
$python = Join-Path $source '.venv\Scripts\python.exe'
$database = 'C:\Users\Georg\AppData\Local\CharacterSheetApp\characters.db'
& $python -c 'import sqlite3,sys; source=sqlite3.connect("file:"+sys.argv[1]+"?mode=ro",uri=True); dest=sqlite3.connect(sys.argv[2]); source.backup(dest); print("Database backup:",dest.execute("PRAGMA integrity_check").fetchone()[0]); dest.close(); source.close()' $database (Join-Path $backup 'live-characters.db')
if ($LASTEXITCODE -ne 0) { throw 'Database backup failed; deployment cancelled.' }
foreach ($relative in $files) {
    $original = Join-Path $source $relative
    $installed = Join-Path $destination $relative
    Copy-Item -LiteralPath $original -Destination $installed -Force
    if ((Get-FileHash -LiteralPath $original).Hash -ne (Get-FileHash -LiteralPath $installed).Hash) {
        throw "Hash mismatch: $relative"
    }
}
Write-Output "Deployed $($files.Count) files to the normal installation. Backup: $backup"
