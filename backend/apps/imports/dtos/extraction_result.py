from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class ExtractionResult:
    csvs: Dict[str, List[Dict[str, str]]] = field(default_factory=dict)
    missing: List[str] = field(default_factory=list)