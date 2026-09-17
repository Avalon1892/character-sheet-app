$ErrorActionPreference = 'Stop'
$source = Split-Path -Parent $PSScriptRoot
$destination = 'C:\Users\Georg\Desktop\Character Sheet App'
$backup = Join-Path $destination ('.backups\optional-traditions-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
$files = @(
    'app\optional_traditions.py', 'app\tradition_schema.py', 'app\catalogs.py', 'app\database.py',
    'app\ui\optional_traditions.py', 'app\ui\main_window.py', 'app\ui\character_sheet.py',
    'app\ui\pages.py', 'app\ui\refined\pages.py', 'app\ui\refined\components.py',
    'app\ui\refined\actions.py', 'app\building_blocks\registry.py',
    'data\pf1e\optional_traditions.json', 'tests\test_optional_traditions.py',
    'tools\import_optional_traditions.py', 'tools\check_optional_traditions.py', 'OPTIONAL_TRADITIONS.md'
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
& (Join-Path $source '.venv\Scripts\python.exe') (Join-Path $source 'tools\backup_character_database.py') 'C:\Users\Georg\AppData\Local\CharacterSheetApp\characters.db' (Join-Path $backup 'characters.db')
if ($LASTEXITCODE -ne 0) { throw 'Database backup failed' }
foreach ($relative in $files) {
    $installed = Join-Path $destination $relative
    New-Item -ItemType Directory -Path (Split-Path -Parent $installed) -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $source $relative) -Destination $installed -Force
    if ((Get-FileHash (Join-Path $source $relative)).Hash -ne (Get-FileHash $installed).Hash) { throw 'Deployment verification failed' }
}
Write-Output "Normal installation updated. Backup: $backup"
