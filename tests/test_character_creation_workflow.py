from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.ability_score_generation import (
    ABILITY_ARRAYS_BY_KEY,
    ability_point_buy_cost,
)
from app.character_creation import CharacterCreationDraft, apply_character_creation_draft
from app.database import CharacterRepository
from app.models import RaceTraitChoice
from app.ui.ability_assignment_widget import AbilityAssignmentWidget
from app.ui.character_creation_dialog import GuidedCharacterCreationDialog


class AbilityScoreGenerationTests(unittest.TestCase):
    def test_registered_arrays_match_their_named_point_buy_budgets(self) -> None:
        expected = {"standard": 15, "high": 20, "epic": 25}
        for key, budget in expected.items():
            with self.subTest(key=key):
                scores = ABILITY_ARRAYS_BY_KEY[key].default_assignment()
                self.assertEqual(budget, ability_point_buy_cost(scores))


class CharacterCreationWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def test_creator_uses_clear_five_step_flow_and_standard_array(self) -> None:
        dialog = GuidedCharacterCreationDialog()
        self.assertEqual(5, dialog.pages.count())
        self.assertEqual(
            ["1   Identity", "2   Race", "3   Class", "4   Abilities", "5   Review"],
            [dialog.steps.item(row).text() for row in range(dialog.steps.count())],
        )
        self.assertEqual("standard", dialog.ability_assignment.method.currentData())
        self.assertEqual(
            ABILITY_ARRAYS_BY_KEY["standard"].default_assignment(),
            dialog.ability_assignment.scores(),
        )
        dialog.close()

    def test_flexible_racial_increase_is_assigned_on_the_race_step(self) -> None:
        dialog = GuidedCharacterCreationDialog()
        dialog._race_selection = {
            "race_key": "human",
            "race_name": "Human",
            "size": "Medium",
            "ability_choice": "",
            "variant_key": "",
            "alternate_trait_keys": (),
            "trait_choices": (),
        }
        dialog.race.setText("Human")
        dialog._rebuild_race_distribution()
        self.assertFalse(dialog.race_distribution.isHidden())
        combo = dialog._base_racial_ability
        combo.setCurrentIndex(combo.findData("dexterity"))
        self.assertEqual("dexterity", dialog.draft.race_ability_choice)
        self.assertEqual(2, dialog.ability_assignment._racial_adjustments["dexterity"])
        dialog.close()

    def test_trait_based_multiple_racial_increases_remain_editable_on_race_step(self) -> None:
        dialog = GuidedCharacterCreationDialog()
        choice_key = ("race-alt-trait:human:dual-talent", "ability_scores")
        dialog._race_selection = {
            "race_key": "human",
            "race_name": "Human",
            "size": "Medium",
            "ability_choice": "",
            "variant_key": "",
            "alternate_trait_keys": (choice_key[0],),
            "trait_choices": (
                RaceTraitChoice(choice_key[0], choice_key[1], ("strength", "dexterity")),
            ),
        }
        dialog.race.setText("Human")
        dialog._rebuild_race_distribution()
        first, _second = dialog._race_trait_ability_controls[choice_key]
        first.setCurrentIndex(first.findData("constitution"))
        saved = next(
            choice for choice in dialog.draft.race_trait_choices
            if (choice.trait_key, choice.choice_key) == choice_key
        )
        self.assertEqual(("constitution", "dexterity"), saved.values)
        self.assertEqual(2, dialog.ability_assignment._racial_adjustments["constitution"])
        self.assertEqual(2, dialog.ability_assignment._racial_adjustments["dexterity"])
        dialog.close()

    def test_array_assignment_swaps_used_values_instead_of_duplicating_them(self) -> None:
        widget = AbilityAssignmentWidget()
        strength = widget._array["strength"]
        strength.setCurrentIndex(1)
        scores = widget.scores()
        self.assertEqual(14, scores["strength"])
        self.assertEqual(15, scores["dexterity"])
        self.assertCountEqual(
            ABILITY_ARRAYS_BY_KEY["standard"].scores,
            tuple(scores.values()),
        )
        widget.close()

    def test_array_can_be_unlocked_for_manual_editing_without_losing_scores(self) -> None:
        widget = AbilityAssignmentWidget()
        before = widget.scores()
        widget._convert_to_manual()
        self.assertEqual("manual", widget.method.currentData())
        self.assertEqual(before, widget.scores())
        widget._manual["strength"].setValue(18)
        self.assertEqual(18, widget.scores()["strength"])
        widget.close()

    def test_draft_persists_full_catalog_race_and_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository = CharacterRepository(Path(directory) / "characters.db")
            character = repository.create_character("Creator", "Pathfinder 1e")
            choice = RaceTraitChoice(
                "race-alt-trait:human:dual-talent",
                "ability_scores",
                ("strength", "dexterity"),
            )
            draft = CharacterCreationDraft(
                "Creator",
                "Pathfinder 1e",
                player_name="Player",
                race="Human",
                alignment="NG",
                deity="Desna",
                size="Medium",
                race_key="human",
                race_alternate_trait_keys=("race-alt-trait:human:dual-talent",),
                race_trait_choices=(choice,),
                abilities=ABILITY_ARRAYS_BY_KEY["standard"].default_assignment(),
            )
            apply_character_creation_draft(repository, character, draft)
            details = repository.get_character_details(character)
            self.assertEqual("Player", details.player_name)
            self.assertEqual("Desna", details.deity)
            self.assertEqual("human", details.race_key)
            self.assertEqual((choice,), details.race_trait_choices)
            self.assertEqual(15, repository.get_ability_scores(character)["strength"])
            repository.close()


if __name__ == "__main__":
    unittest.main()
