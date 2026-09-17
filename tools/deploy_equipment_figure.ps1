$ErrorActionPreference = 'Stop'
$source = Split-Path -Parent $PSScriptRoot
$destination = 'C:\Users\Georg\Desktop\Character Sheet App'
$backup = Join-Path $destination ('.backups\equipment-figure-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
$files = @(
    'app\equipment_wearing.py', 'app\ui\equipment_drag.py', 'app\ui\equipment_figure.py',
    'app\ui\inventory_dialog.py', 'app\ui\character_sheet.py', 'app\ui\sheet_sections.py',
    'app\ui\refined\actions.py', 'tests\test_equipment_figure.py',
    'tests\test_refined_sheet.py', 'tools\check_equipment_figure.py', 'EQUIPMENT_FIGURE.md'
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
