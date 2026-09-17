$ErrorActionPreference = 'Stop'
$source = Split-Path -Parent $PSScriptRoot
$destination = 'C:\Users\Georg\Desktop\Character Sheet App'
$backup = Join-Path $destination ('.backups\dialog-skills-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
$files = @(
    'app\ui\main_window.py',
    'app\ui\dialog_theme.py',
    'app\ui\sphere_colors.py',
    'app\ui\refined\item_colors.py',
    'app\ui\refined\sheet.py',
    'app\ui\martial_book_dialog.py',
    'app\ui\spellbook_dialog.py',
    'tests\test_dialog_colors.py',
    'tests\test_refined_sheet.py',
    'tools\check_dialog_skills.py'
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
& $python -c 'import sqlite3,sys; source=sqlite3.connect("file:"+sys.argv[1]+"?mode=ro",uri=True); dest=sqlite3.connect(sys.argv[2]); source.backup(dest); result=dest.execute("PRAGMA integrity_check").fetchone()[0]; print("Database backup:",result); dest.close(); source.close(); sys.exit(0 if result=="ok" else 1)' $database (Join-Path $backup 'live-characters.db')
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
