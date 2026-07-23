from collections import defaultdict


def group_rows(rows, key):
    """Group mapping-like database rows by a column without issuing more queries."""
    grouped = defaultdict(list)
    for row in rows:
        grouped[row[key]].append(row)
    return dict(grouped)
