from __future__ import annotations

import csv
import io
import zipfile
from typing import Dict, List, Optional, Sequence, Set, Tuple, Union

from apps.imports.dtos.extraction_result import ExtractionResult
from apps.imports.exceptions import LetterboxdImportError


CANONICAL_FILES: Dict[str, List[str]] = {
    "ratings.csv": ["ratings.csv"],
    "diary.csv": ["diary.csv"],
    "watchlist.csv": ["watchlist.csv"],
    "watched.csv": ["watched.csv"],
    "liked_films.csv": ["likes/films.csv"],
}
ALL_CANONICAL: Set[str] = set(CANONICAL_FILES)

EXPECTED_COLUMNS: Dict[str, set] = {
    "ratings.csv": {"Name", "Year", "Rating"},
    "diary.csv": {"Name", "Year", "Rating", "Watched Date"},
    "watched.csv": {"Name", "Year"},
    "watchlist.csv": {"Name", "Year"},
    "liked_films.csv": {"Name", "Year"},
}

SingleUpload = Union[object, Tuple[object, Optional[str]]]


def _basename_lower(path: str) -> str:
    return path.rsplit("/", 1)[-1].strip().lower()


def _parse_csv_text(text: str, source_name: str) -> Tuple[List[str], List[Dict[str, str]]]:
    try:
        reader = csv.DictReader(io.StringIO(text))
        rows = list(reader)
    except csv.Error as exc:
        raise LetterboxdImportError(
            f"Could not parse '{source_name}' as CSV: {exc}"
        ) from exc

    if reader.fieldnames is None:
        raise LetterboxdImportError(f"'{source_name}' is empty or has no header row.")

    return list(reader.fieldnames), rows


def _decode(raw: bytes, source_name: str) -> str:
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise LetterboxdImportError(f"Could not decode '{source_name}' (unknown encoding).")


def _validate_columns(canonical: str, fieldnames: List[str], source_name: str) -> None:
    expected = EXPECTED_COLUMNS.get(canonical)
    if expected is None:
        return
    
    missing_columns = expected - set(fieldnames)

    if missing_columns:
        raise LetterboxdImportError(
            f"'{source_name}' was matched as {canonical}, but its header is "
            f"missing expected column(s): {', '.join(sorted(missing_columns))}. "
            "It may have been renamed and doesn't actually contain that data."
        )


def _match_canonical(basename_or_path: str) -> Optional[str]:
    base = _basename_lower(basename_or_path)
    for canonical, variants in CANONICAL_FILES.items():
        if any(base == _basename_lower(v) for v in variants):
            return canonical
        
    return None


def _resolve_include_and_required(
    include: Optional[Set[str]],
    required: Optional[Set[str]],
) -> Tuple[Set[str], Set[str]]:
    resolved_include = set(include) if include is not None else set(ALL_CANONICAL)
    resolved_required = set(required) if required is not None else set()

    unknown = (resolved_include | resolved_required) - ALL_CANONICAL
    if unknown:
        raise ValueError(
            f"Unknown canonical file name(s): {', '.join(sorted(unknown))}. "
            f"Valid names are: {', '.join(sorted(ALL_CANONICAL))}."
        )

    not_included = resolved_required - resolved_include
    if not_included:
        raise ValueError(
            f"'required' contains file(s) not present in 'include': "
            f"{', '.join(sorted(not_included))}. Add them to 'include' too, "
            "or drop them from 'required'."
        )

    return resolved_include, resolved_required


def _check_required(result: ExtractionResult, required: Set[str]) -> None:
    missing_required = required - set(result.csvs)
    if missing_required:
        raise LetterboxdImportError(
            "The export is missing the required CSV(s): "
            f"{', '.join(sorted(missing_required))}."
        )


def _split_upload(upload: SingleUpload) -> Tuple[object, Optional[str]]:
    """Normalizes an upload into (file_obj, filename). Accepts either a
    plain file-like object (using its `.name` attribute, Django-style), or
    an explicit (file_obj, filename) tuple."""
    if isinstance(upload, tuple):
        file_obj, filename = upload
    else:
        file_obj, filename = upload, getattr(upload, "name", None)

    return file_obj, filename


def extract_letterboxd_csvs(
    uploads: Union[SingleUpload, Sequence[SingleUpload]],
    include: Optional[Set[str]] = None,
    required: Optional[Set[str]] = None,
) -> ExtractionResult:
    resolved_include, resolved_required = _resolve_include_and_required(include, required)

    upload_list: List[SingleUpload] = uploads if isinstance(uploads, list) else [uploads]

    if not upload_list:
        raise LetterboxdImportError("No files were uploaded.")

    read_uploads: List[Tuple[bytes, Optional[str]]] = []
    for item in upload_list:
        file_obj, filename = _split_upload(item)
        read_uploads.append((file_obj.read(), filename))

    if len(read_uploads) == 1:
        raw, filename = read_uploads[0]
        name_hint = (filename or "").lower()
        if name_hint.endswith(".zip") or raw[:2] == b"PK":
            return _extract_from_zip(raw, filename or "export.zip", resolved_include, resolved_required)
        return _extract_from_standalone_csvs(read_uploads, resolved_include, resolved_required)

    for raw, filename in read_uploads:
        name_hint = (filename or "").lower()
        if name_hint.endswith(".zip") or raw[:2] == b"PK":
            raise LetterboxdImportError(
                f"'{filename or 'unnamed file'}' looks like a zip archive; "
                "upload a zip on its own, not alongside other files."
            )

    return _extract_from_standalone_csvs(read_uploads, resolved_include, resolved_required)


def _extract_from_standalone_csvs(
    raw_uploads: List[Tuple[bytes, Optional[str]]],
    include: Set[str],
    required: Set[str],
) -> ExtractionResult:
    found: Dict[str, List[Dict[str, str]]] = {}

    for raw, filename in raw_uploads:
        if not filename:
            raise LetterboxdImportError(
                "Every standalone CSV upload needs its original filename "
                "to be identified."
            )

        canonical = _match_canonical(filename)
        if canonical is None:
            raise LetterboxdImportError(
                f"'{filename}' is not one of the expected CSVs from a "
                f"Letterboxd export."
            )
        if canonical not in include:
            raise LetterboxdImportError(
                f"'{filename}' (matched as {canonical}) isn't needed for "
                "this import and was rejected."
            )
        if canonical in found:
            raise LetterboxdImportError(
                f"'{filename}' duplicates a file already uploaded as "
                f"{canonical}."
            )

        text = _decode(raw, filename)
        fieldnames, rows = _parse_csv_text(text, filename)
        _validate_columns(canonical, fieldnames, filename)
        found[canonical] = rows

    result = ExtractionResult(
        csvs=found,
        missing=[c for c in include if c not in found],
    )
    _check_required(result, required)

    return result


def _extract_from_zip(
    raw: bytes,
    source_name: str,
    include: Set[str],
    required: Set[str],
) -> ExtractionResult:
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile as exc:
        raise LetterboxdImportError(
            f"'{source_name}' is not a valid .zip or is corrupted."
        ) from exc

    bad_file = zf.testzip()
    if bad_file is not None:
        raise LetterboxdImportError(
            f"The zip '{source_name}' is damaged (corrupt file: {bad_file})."
        )

    found: Dict[str, List[Dict[str, str]]] = {}
    for info in zf.infolist():
        if info.is_dir():
            continue
        canonical = _match_canonical(info.filename)
        if canonical is None or canonical not in include or canonical in found:
            continue
        text = _decode(zf.read(info), info.filename)
        fieldnames, rows = _parse_csv_text(text, info.filename)
        _validate_columns(canonical, fieldnames, info.filename)
        found[canonical] = rows

    result = ExtractionResult(
        csvs=found,
        missing=[c for c in include if c not in found],
    )
    _check_required(result, required)

    return result
