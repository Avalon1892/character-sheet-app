$ErrorActionPreference = 'Stop'
$source = Split-Path -Parent $PSScriptRoot
$destination = 'C:\Users\Georg\Desktop\Character Sheet App'
$backup = Join-Path $destination ('.backups\movement-container-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
$files = @('app\athletics_rules.py', 'app\services\character_calculations.py', 'app\ui\character_sheet.py', 'app\ui\dialog_theme.py', 'tests\test_athletics_rules.py')
foreach ($relative in $files) {
    $saved = Join-Path $backup $relative
    New-Item -ItemType Directory -Path (Split-Path -Parent $saved) -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $destination $relative) -Destination $saved
}
& (Join-Path $source '.venv\Scripts\python.exe') -c 'import sqlite3,sys; s=sqlite3.connect("file:"+sys.argv[1]+"?mode=ro",uri=True); d=sqlite3.connect(sys.argv[2]); s.backup(d); assert d.execute("PRAGMA integrity_check").fetchone()[0]=="ok"; d.close(); s.close()' 'C:\Users\Georg\AppData\Local\CharacterSheetApp\characters.db' (Join-Path $backup 'characters.db')
if ($LASTEXITCODE -ne 0) { throw 'Database backup failed' }
foreach ($relative in $files) {
    Copy-Item -LiteralPath (Join-Path $source $relative) -Destination (Join-Path $destination $relative) -Force
    if ((Get-FileHash (Join-Path $source $relative)).Hash -ne (Get-FileHash (Join-Path $destination $relative)).Hash) { throw 'Deployment verification failed' }
}
Write-Output "Normal installation updated. Backup: $backup"
