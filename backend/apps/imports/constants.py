from typing import Dict, List, Set


RATINGS_CSV = "ratings.csv"
DIARY_CSV = "diary.csv"
WATCHED_CSV = "watched.csv"
LIKED_CSV = "liked_films.csv"
WATCHLIST_CSV = "watchlist.csv"


CANONICAL_FILES: Dict[str, List[str]] = {
    RATINGS_CSV: [RATINGS_CSV],
    DIARY_CSV: [DIARY_CSV],
    WATCHED_CSV: [WATCHED_CSV],
    LIKED_CSV: ["likes/films.csv"],
    WATCHLIST_CSV: [WATCHLIST_CSV],
}

ALL_CANONICAL: Set[str] = set(CANONICAL_FILES)


COMMON_COLUMNS = {"Name", "Year"}
RATING_COLUMNS = COMMON_COLUMNS | {"Rating"}
DIARY_COLUMNS = RATING_COLUMNS | {"Watched Date"}

EXPECTED_COLUMNS: Dict[str, set] = {
    RATINGS_CSV: RATING_COLUMNS,
    DIARY_CSV: DIARY_COLUMNS,
    WATCHED_CSV: COMMON_COLUMNS,
    LIKED_CSV: COMMON_COLUMNS,
    WATCHLIST_CSV: COMMON_COLUMNS,
}
