from dataclasses import dataclass


@dataclass(slots=True)
class RatingMatrix:
    by_user: dict[int, dict[int, float]]
    by_movie: dict[int, dict[int, float]]