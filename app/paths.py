import os
from pathlib import Path


APP_DATA_DIR = Path(
    os.environ.get(
        "CHARACTER_SHEET_DATA_DIR",
        Path.home() / "AppData" / "Local" / "CharacterSheetApp",
    )
).expanduser().resolve()
DATABASE_PATH = APP_DATA_DIR / "characters.db"
