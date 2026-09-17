from __future__ import annotations

import unittest

from app.prodigy_content import (
    SPHERE_PRODIGY_OPTIONS,
    UNIVERSAL_PRODIGY_OPTIONS,
    prodigy_codex_html,
)


class ProdigyCodexCategoryTests(unittest.TestCase):
    def test_surface_cut_is_presented_as_an_opener(self) -> None:
        html = prodigy_codex_html()

        self.assertIn("<b>Opener — Surface Cut</b>", html)
        self.assertNotIn("<b>Finisher — Surface Cut</b>", html)

    def test_every_sequence_option_uses_its_recorded_category(self) -> None:
        html = prodigy_codex_html()

        for option in (*UNIVERSAL_PRODIGY_OPTIONS, *SPHERE_PRODIGY_OPTIONS):
            with self.subTest(name=option.name, sphere=option.sphere):
                self.assertIn(
                    f"<b>{option.option_type} — {option.name}</b>",
                    html,
                )

    def test_sequence_descriptions_do_not_hide_link_thresholds(self) -> None:
        vague_phrases = (
            "improves at",
            "stronger action options",
            "the available action improves",
        )

        for option in (*UNIVERSAL_PRODIGY_OPTIONS, *SPHERE_PRODIGY_OPTIONS):
            with self.subTest(name=option.name, sphere=option.sphere):
                description = option.description.casefold()
                self.assertFalse(
                    any(phrase in description for phrase in vague_phrases),
                    option.description,
                )


if __name__ == "__main__":
    unittest.main()
