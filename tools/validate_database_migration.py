from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import CharacterRepository


def main() -> None:
    repository = CharacterRepository(Path(sys.argv[1]))
    try:
        characters = repository.list_characters()
        print(f"characters={len(characters)}")
        for character in characters:
            profile = repository.get_casting_profile(character.id)
            options = repository.list_sequence_options(character.id)
            classes = repository.list_class_levels(character.id)
            built_in = sum(option.built_in for option in options)
            print(
                f"id={character.id} name={character.name!r} "
                f"classes={[(item.class_name, item.level) for item in classes]!r} "
                f"spell_points_misc={profile.spell_points_misc} "
                f"base_sequence_options={built_in}"
            )
    finally:
        repository.close()


if __name__ == "__main__":
    main()
