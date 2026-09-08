from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class ImportSummary:
    imported: Dict[str, int] = field(default_factory=dict)
    missing: List[str] = field(default_factory=list)