from dataclasses import dataclass

from apps.comparisons.models import Comparison


@dataclass(slots=True)
class ComparisonResult:
    comparison: Comparison
    metrics: dict
    narrative: str
    recommendations: list[dict]
    narrative_available: bool