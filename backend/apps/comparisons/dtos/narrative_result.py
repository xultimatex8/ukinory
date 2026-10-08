from dataclasses import dataclass, field


@dataclass(slots=True)
class NarrativeResult:
    summary: str
    reasons: dict[int, str]
    individual: dict[str, str] = field(default_factory=dict)