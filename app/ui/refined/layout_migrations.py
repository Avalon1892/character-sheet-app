"""One-time, conservative default upgrades; explicit user layouts always win."""
from __future__ import annotations

import json


SKILLS_REFERENCE_LAYOUT = "skills-reference-columns-v1"


def migrate_traditions_character_page(presentation, character_id):
    """Correct the old Equipment default without moving user-placed blocks."""
    connection = presentation.connection
    key = 'traditions-character-page-v1'
    if connection.execute(
        'SELECT 1 FROM sheet_presentation_migrations WHERE character_id=? AND migration_key=?',
        (character_id, key),
    ).fetchone():
        return
    with connection.batch():
        for instance in presentation.list_instances(character_id):
            snapshot = instance.template_snapshot
            if (snapshot.get('section_key') in ('traditions', 'optional_traditions')
                    and instance.tab_key == 'inventory' and snapshot.get('default_tab') == 'inventory'
                    and (instance.x, instance.y) == (24, 24)):
                connection.execute(
                    'UPDATE sheet_block_instances SET tab_key=?,template_snapshot_json=? WHERE id=?',
                    ('build', json.dumps({**snapshot, 'default_tab': 'build'}), instance.id),
                )
        connection.execute(
            'INSERT INTO sheet_presentation_migrations (character_id,migration_key) VALUES (?,?)',
            (character_id, key),
        )


def migrate_skills_reference_layout(presentation, character_id, state):
    """Move only an untouched old Special Abilities block to its new default.

    The saved template records which factory composition a character started
    with. Keeping that snapshot for customized characters lets the UI preserve
    their previous baseline without inventing absolute positions for it.
    """
    connection=presentation.connection
    if connection.execute(
        "SELECT 1 FROM sheet_presentation_migrations WHERE character_id=? AND migration_key=?",
        (character_id,SKILLS_REFERENCE_LAYOUT),
    ).fetchone():
        return
    instances={instance.template_snapshot.get("section_key"):instance
               for instance in presentation.list_instances(character_id)}
    abilities=instances.get("special_abilities")
    skills=instances.get("skills")
    layout=state.get("layout",{})
    try:
        freeform=json.loads(layout.get("freeform","{}") or "{}")
        order=json.loads(layout.get("layout","{}") or "{}")
    except (TypeError,ValueError):
        freeform=None
        order=None
    untouched=isinstance(freeform,dict) and not order
    for key,instance,old_page in (("skills",skills,"skills"),
                                  ("special_abilities",abilities,"abilities")):
        if instance is None:
            untouched=False
            continue
        snapshot=instance.template_snapshot
        untouched=untouched and (
            instance.tab_key==old_page
            and snapshot.get("default_tab")==old_page
            and instance.visible
            and (instance.x,instance.y)==(24,24)
            and (instance.width,instance.height)==(snapshot.get("width"),snapshot.get("height"))
            and key not in (freeform or {})
            and not layout.get("sizes/"+key)
            and not presentation.list_cell_overrides(instance.id)
        )
    with connection.batch():
        if untouched:
            snapshot={**abilities.template_snapshot,"default_tab":"skills"}
            connection.execute(
                "UPDATE sheet_block_instances SET tab_key=?,template_snapshot_json=? WHERE id=?",
                ("skills",json.dumps(snapshot),abilities.id),
            )
        connection.execute(
            "INSERT INTO sheet_presentation_migrations (character_id,migration_key) VALUES (?,?)",
            (character_id,SKILLS_REFERENCE_LAYOUT),
        )
