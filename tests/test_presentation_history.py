from __future__ import annotations

import unittest

from app.presentation_history import PresentationHistory, PresentationSnapshot


class PresentationHistoryTests(unittest.TestCase):
    def test_bounded_character_specific_undo_and_redo(self) -> None:
        current = {"value": 0, "character": 1}

        def capture():
            return PresentationSnapshot(
                current["character"], {"value": str(current["value"])}, {}, "core"
            )

        def apply(snapshot):
            current["character"] = snapshot.character_id
            current["value"] = int(snapshot.layout["value"])

        history = PresentationHistory(capture, apply, limit=10)
        history.record("Move box", lambda: current.update(value=5))
        self.assertTrue(history.can_undo(1))
        self.assertEqual("Move box", history.undo_description(1))
        self.assertTrue(history.undo(1))
        self.assertEqual(0, current["value"])
        self.assertTrue(history.redo(1))
        self.assertEqual(5, current["value"])

        current["character"] = 2
        self.assertFalse(history.can_undo(2))
        history.record("Resize box", lambda: current.update(value=9))
        self.assertTrue(history.can_undo(2))
        self.assertTrue(history.can_undo(1))

    def test_noop_and_failed_operations_do_not_enter_history(self) -> None:
        current = {"value": 0}
        capture = lambda: PresentationSnapshot(1, {"value": str(current["value"])}, {})
        history = PresentationHistory(capture, lambda _snapshot: None)
        history.record("No change", lambda: None)
        self.assertFalse(history.can_undo(1))
        with self.assertRaises(RuntimeError):
            history.record("Failure", lambda: (_ for _ in ()).throw(RuntimeError()))
        self.assertFalse(history.can_undo(1))

    def test_discard_removes_deleted_character_history_and_pending_change(self) -> None:
        current = {"value": 0, "character": 1}
        capture = lambda: PresentationSnapshot(
            current["character"], {"value": str(current["value"])}, {}
        )
        history = PresentationHistory(capture, lambda _snapshot: None)
        history.record("Move", lambda: current.update(value=1))
        self.assertTrue(history.can_undo(1))
        self.assertTrue(history.begin("Resize"))

        history.discard(1)

        self.assertFalse(history.can_undo(1))
        self.assertFalse(history.can_redo(1))
        self.assertFalse(history.commit())


if __name__ == "__main__":
    unittest.main()
