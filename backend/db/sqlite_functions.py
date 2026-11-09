from backend.db.search import casefold, fuzzy_word_in


def register_sqlite_functions(conn) -> None:
    conn.create_function('fuzzy_word_in', 2, fuzzy_word_in)
    conn.create_function('casefold', 1, casefold, deterministic=True)
