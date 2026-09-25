"""Encounter budgets and additive campaign persistence; no character mutations."""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
import json
import sqlite3

ENCOUNTER_RULES_URL = "https://legacy.aonprd.com/coreRuleBook/gamemastering.html"
XP_BY_CR = dict(zip(("1/8", "1/6", "1/4", "1/3", "1/2", *(str(i) for i in range(1, 26))),
                   (50, 65, 100, 135, 200, 400, 600, 800, 1200, 1600, 2400, 3200,
                    4800, 6400, 9600, 12800, 19200, 25600, 38400, 51200, 76800,
                    102400, 153600, 204800, 307200, 409600, 614400, 819200, 1228800, 1638400)))
DIFFICULTIES = {"Easy": -1, "Average": 0, "Challenging": 1, "Hard": 2, "Epic": 3}


def parse_party_levels(text: str) -> tuple[int, ...]:
    try:
        levels = tuple(int(value.strip()) for value in text.split(","))
    except ValueError:
        raise ValueError("Enter party levels separated by commas, for example 5, 5, 5, 5.") from None
    if not 1 <= len(levels) <= 30 or any(not 1 <= level <= 40 for level in levels):
        raise ValueError("Use 1–30 characters, each of level 1–40.")
    return levels


def average_party_level(levels: tuple[int, ...]) -> int:
    levels = parse_party_levels(",".join(map(str, levels)))
    average = int((Decimal(sum(levels)) / len(levels)).quantize(Decimal(1), rounding=ROUND_HALF_UP))
    return average + (1 if len(levels) >= 6 else -1 if len(levels) <= 3 else 0)


@dataclass(frozen=True)
class EncounterBudget:
    xp: int
    unknown: tuple[str, ...]
    apl: int
    target_cr: int
    target_xp: int | None
    equivalent_cr: str


def encounter_budget(entries: dict[str, dict], members: dict[str, int], levels: tuple[int, ...], difficulty: str) -> EncounterBudget:
    if difficulty not in DIFFICULTIES:
        raise ValueError("Unknown encounter difficulty")
    xp, unknown = 0, []
    for key, quantity in members.items():
        if type(quantity) is not int or not 1 <= quantity <= 999:
            raise ValueError("Creature quantities must be between 1 and 999.")
        entry = entries.get(key)
        value = entry.get("xp") if entry else None
        if value is None:
            unknown.append(entry["name"] if entry else key)
        else:
            xp += int(value) * quantity
    apl = average_party_level(levels)
    target = apl + DIFFICULTIES[difficulty]
    pairs = list(XP_BY_CR.items())
    equivalent = "No creatures" if not members else "Below CR 1/8"
    if unknown:
        equivalent = "Unknown (missing XP)"
    elif xp > pairs[-1][1]:
        equivalent = "Above CR 25"
    else:
        for index, (cr, value) in enumerate(pairs):
            if xp == value:
                equivalent = f"CR {cr}"
                break
            if xp < value and index:
                equivalent = f"Between CR {pairs[index - 1][0]} and {cr}"
                break
    return EncounterBudget(xp, tuple(unknown), apl, target, XP_BY_CR.get(str(target)), equivalent)


class EncounterRepository:
    """Uses the existing application connection; saves are explicit and atomic."""
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection
        self.connection.execute("""CREATE TABLE IF NOT EXISTS encounters (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
            payload TEXT NOT NULL, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        self.connection.commit()

    def list(self) -> list[tuple[int, str]]:
        return [(row[0], row[1]) for row in self.connection.execute("SELECT id,name FROM encounters ORDER BY name COLLATE NOCASE,id")]

    def load(self, encounter_id: int) -> dict:
        row = self.connection.execute("SELECT name,payload FROM encounters WHERE id=?", (encounter_id,)).fetchone()
        if row is None:
            raise ValueError("This encounter no longer exists.")
        return {"name": row[0], **json.loads(row[1])}

    def save(self, name: str, members: dict[str, int], levels: tuple[int, ...], difficulty: str, notes: str, encounter_id=None) -> int:
        name = name.strip()
        if not name or len(name) > 200:
            raise ValueError("Give the encounter a name (up to 200 characters).")
        encounter_budget({}, members, levels, difficulty)  # Same input contract as the live preview.
        payload = json.dumps({"members": members, "levels": levels, "difficulty": difficulty, "notes": notes})
        with self.connection:
            if encounter_id is None:
                cursor = self.connection.execute("INSERT INTO encounters(name,payload) VALUES (?,?)", (name, payload))
                return int(cursor.lastrowid)
            cursor = self.connection.execute("UPDATE encounters SET name=?,payload=?,updated_at=CURRENT_TIMESTAMP WHERE id=?", (name, payload, encounter_id))
            if cursor.rowcount != 1:
                raise ValueError("This encounter no longer exists; save a new copy.")
        return encounter_id

    def delete(self, encounter_id: int) -> None:
        with self.connection:
            self.connection.execute("DELETE FROM encounters WHERE id=?", (encounter_id,))
