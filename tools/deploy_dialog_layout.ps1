$ErrorActionPreference = 'Stop'
$source = Split-Path -Parent $PSScriptRoot
$destination = 'C:\Users\Georg\Desktop\Character Sheet App'
$backup = Join-Path $destination ('.backups\dialog-layout-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
$files = @('app\ui\dialog_layout.py', 'app\ui\dialog_theme.py', 'app\ui\catalog_presentation.py',
    'app\ui\class_choice_dialog.py', 'app\ui\class_power_dialog.py', 'tests\test_dialog_layout.py',
    'tests\test_catalog_presentation.py', 'tools\review_dialog_layouts.py', 'DIALOG_LAYOUT.md')
New-Item -ItemType Directory -Path $backup -Force | Out-Null
foreach ($relative in $files) {
    $installed = Join-Path $destination $relative
    if (Test-Path -LiteralPath $installed) {
        $saved = Join-Path $backup $relative
        New-Item -ItemType Directory -Path (Split-Path -Parent $saved) -Force | Out-Null
        Copy-Item -LiteralPath $installed -Destination $saved
    }
}
& (Join-Path $source '.venv\Scripts\python.exe') (Join-Path $source 'tools\backup_character_database.py') 'C:\Users\Georg\AppData\Local\CharacterSheetApp\characters.db' (Join-Path $backup 'characters.db')
if ($LASTEXITCODE -ne 0) { throw 'Database backup failed' }
foreach ($relative in $files) {
    $installed = Join-Path $destination $relative
    New-Item -ItemType Directory -Path (Split-Path -Parent $installed) -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $source $relative) -Destination $installed -Force
    if ((Get-FileHash (Join-Path $source $relative)).Hash -ne (Get-FileHash $installed).Hash) { throw 'Deployment verification failed' }
}
Write-Output "Normal installation updated. Backup: $backup"
