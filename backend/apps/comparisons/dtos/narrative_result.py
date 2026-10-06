from dataclasses import dataclass


@dataclass(slots=True)
class NarrativeResult:
    summary: str
    reasons: dict[int, str]