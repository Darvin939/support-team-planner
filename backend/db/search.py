"""Shared Unicode and fuzzy semantics; PostgreSQL filters IDs before pagination."""


def casefold(value):
    return (value or '').casefold()


def fuzzy_word_in(text, word):
    if not text or not word:
        return False
    text, word = text.lower(), word.lower()
    if word in text:
        return True
    length = len(word)
    if length < 3:
        return False
    max_errors = max(1, length // 7)
    for index in range(len(text) - length + 1):
        if sum(left != right for left, right in zip(text[index:index + length], word)) <= max_errors:
            return True
    return False


def task_matches(name, description, search):
    return all(fuzzy_word_in(name, word) or fuzzy_word_in(description, word) for word in search.split())


def matching_ids_clause(conn, backend, query, params, matches, column='id'):
    """Read every access-limited candidate, retaining only matching IDs."""
    cursor = backend.candidate_cursor(conn, query, params)
    ids = set()
    try:
        while True:
            rows = cursor.fetchmany(1000)
            if not rows:
                break
            ids.update(row[0] for row in rows if matches(row))
    finally:
        cursor.close()
    return '%s = ANY(%s::bigint[])' % (column, backend.placeholder), [sorted(ids)]
