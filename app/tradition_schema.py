"""Lossless migration of the original two-kind tradition constraint."""


def widen_tradition_kinds(connection):
    sql = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='character_traditions'"
    ).fetchone()[0]
    old = "kind IN ('Casting', 'Martial')"
    if old not in sql:
        return
    connection.execute('SAVEPOINT expand_tradition_kinds')
    try:
        sequence = connection.execute(
            "SELECT seq FROM sqlite_sequence WHERE name='character_traditions'"
        ).fetchone()
        revised = sql.replace('CREATE TABLE character_traditions', 'CREATE TABLE expanded_character_traditions')
        revised = revised.replace(old, "kind IN ('Casting', 'Martial', 'Crafting', 'Tinker')")
        connection.execute(revised)
        connection.execute('INSERT INTO expanded_character_traditions SELECT * FROM character_traditions')
        connection.execute('DROP TABLE character_traditions')
        connection.execute('ALTER TABLE expanded_character_traditions RENAME TO character_traditions')
        if sequence:
            connection.execute("UPDATE sqlite_sequence SET seq=MAX(seq, ?) WHERE name='character_traditions'", (sequence[0],))
        connection.execute('RELEASE expand_tradition_kinds')
    except Exception:
        connection.execute('ROLLBACK TO expand_tradition_kinds')
        connection.execute('RELEASE expand_tradition_kinds')
        raise
