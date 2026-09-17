$ErrorActionPreference = 'Stop'
$source = Split-Path -Parent $PSScriptRoot
$destination = 'C:\Users\Georg\Desktop\Character Sheet App'
$backup = Join-Path $destination ('.backups\reference-rules-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
$files = @(
    'app\reference_rules.py', 'app\ui\reference_details.py',
    'app\prodigy_content.py', 'app\ui\main_window.py', 'app\ui\character_sheet.py',
    'data\pf1e\reference_rules.json', 'data\pf1e\reference_rules_LICENSE.txt',
    'tests\test_reference_rules.py', 'tests\test_refined_sheet.py',
    'tools\import_reference_catalog.py', 'tools\check_reference_details.py',
    'REFERENCE_RULES.md'
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
& (Join-Path $source '.venv\Scripts\python.exe') -c 'import sqlite3,sys; s=sqlite3.connect("file:"+sys.argv[1]+"?mode=ro",uri=True); d=sqlite3.connect(sys.argv[2]); s.backup(d); assert d.execute("PRAGMA integrity_check").fetchone()[0]=="ok"; d.close(); s.close()' 'C:\Users\Georg\AppData\Local\CharacterSheetApp\characters.db' (Join-Path $backup 'characters.db')
if ($LASTEXITCODE -ne 0) { throw 'Database backup failed' }
foreach ($relative in $files) {
    $installed = Join-Path $destination $relative
    New-Item -ItemType Directory -Path (Split-Path -Parent $installed) -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $source $relative) -Destination $installed -Force
    if ((Get-FileHash (Join-Path $source $relative)).Hash -ne (Get-FileHash $installed).Hash) { throw 'Deployment verification failed' }
}
Write-Output "Normal installation updated. Backup: $backup"
