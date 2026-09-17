$ErrorActionPreference = "Stop"

if (-not (Test-Path .\.venv\Scripts\python.exe)) {
    throw "The app is not set up yet. Run setup.ps1 first."
}

& .\.venv\Scripts\python.exe main.py

