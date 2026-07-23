from typing import List, Optional


def parse_int_csv(value: Optional[str]) -> Optional[List[int]]:
    return [int(item) for item in value.split(',') if item.strip()] if value else None
