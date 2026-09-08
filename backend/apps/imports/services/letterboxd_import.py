from __future__ import annotations

from typing import List, Optional, Tuple

from apps.imports.dtos.import_summary import ImportSummary
from apps.imports.services.letterboxd_extraction import extract_letterboxd_csvs

Uploads = List[Tuple[object, Optional[str]]]


def import_letterboxd_export(user, uploads: Uploads) -> ImportSummary:
    result = extract_letterboxd_csvs(uploads)

    return ImportSummary(
        imported={canonical: len(rows) for canonical, rows in result.csvs.items()},
        missing=result.missing,
    )
