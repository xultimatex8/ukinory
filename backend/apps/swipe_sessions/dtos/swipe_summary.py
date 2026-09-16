from __future__ import annotations
from dataclasses import dataclass


@dataclass(slots=True)
class SwipeExportSummary:
    rows_written: int
    csv_content: str
