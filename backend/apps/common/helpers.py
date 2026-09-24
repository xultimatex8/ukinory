from typing import Optional


def extract_year(release_date: Optional[str]) -> Optional[int]:
    if not release_date or len(release_date) < 4:
        return None
    try:
        return int(release_date[:4])
    except ValueError:
        return None
