from __future__ import annotations

from typing import List, Optional, Tuple

from apps.imports.dtos.import_summary import ImportSummary
from apps.imports.services.letterboxd_extraction import extract_letterboxd_csvs
from apps.imports.services.letterboxd_persistence import persist_letterboxd_records

Uploads = List[Tuple[object, Optional[str]]]


def import_letterboxd_export(user, uploads: Uploads) -> ImportSummary:
    result = extract_letterboxd_csvs(uploads)
    persisted = persist_letterboxd_records(user, result)

    return ImportSummary(
        imported=persisted,
        missing=result.missing,
    )
