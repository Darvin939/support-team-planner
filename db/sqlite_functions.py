def fuzzy_word_in(text, word):
    """Return whether word occurs in text with the existing fuzzy tolerance."""
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


def register_sqlite_functions(conn) -> None:
    conn.create_function('fuzzy_word_in', 2, fuzzy_word_in)
    conn.create_function('casefold', 1, lambda value: (value or '').casefold(), deterministic=True)
