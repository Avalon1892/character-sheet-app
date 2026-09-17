"""Backward-compatible names for the unified character-audit workflow.

New code should import :mod:`app.ui.character_audit_dialog` directly.  Keeping
this tiny facade preserves extensions which imported the former level-up UI
without retaining a second, divergent implementation.
"""
from app.ui.character_audit_dialog import (
    AuditAction as LevelUpAction,
    CharacterAuditDialog as GuidedLevelUpDialog,
)

__all__ = ("GuidedLevelUpDialog", "LevelUpAction")
