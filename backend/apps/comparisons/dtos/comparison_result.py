from dataclasses import dataclass, field

from apps.comparisons.models import Comparison


@dataclass(slots=True)
class ComparisonResult:
    comparison: Comparison
    metrics: dict
    narrative: str
    recommendations: list[dict]
    narrative_available: bool
    individual: dict[str, str] = field(default_factory=dict)