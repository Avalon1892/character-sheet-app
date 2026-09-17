from app.presentation import readable_tooltip
from app.text_cleanup import repair_mojibake, repair_text_tree


def test_repairs_common_legacy_description_sequences() -> None:
    value = "Take a â2 penalty; donât lose DR 2/â."
    assert repair_mojibake(value) == "Take a –2 penalty; don’t lose DR 2/—."


def test_repairs_catalog_shaped_data_without_touching_unicode() -> None:
    result = repair_text_tree({"description": "An allyâs effect", "name": "Café"})
    assert result == {"description": "An ally’s effect", "name": "Café"}
    assert "â" not in readable_tooltip("Legacy", "Take â2")
