import csv
import io
import zipfile

import pytest

from apps.imports.services.letterboxd_extraction import (
    ALL_CANONICAL,
    ExtractionResult,
    LetterboxdImportError,
    _basename_lower,
    _decode,
    _match_canonical,
    _parse_csv_text,
    _resolve_include_and_required,
    _validate_columns,
    extract_letterboxd_csvs,
)


class NamedBytesIO(io.BytesIO):
    def __init__(self, initial_bytes=b"", name=None):
        super().__init__(initial_bytes)
        self.name = name


def csv_bytes(headers, rows=(), encoding="utf-8", bom=False):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=headers)
    writer.writeheader()
    writer.writerows(rows)
    raw = output.getvalue().encode(encoding)
    if bom:
        raw = b"\xef\xbb\xbf" + raw
    return raw


def zip_bytes(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename, content in files.items():
            zf.writestr(filename, content)
    return buffer.getvalue()



@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("ratings.csv", "ratings.csv"),
        ("folder/ratings.csv", "ratings.csv"),
        ("LIKES/FILMS.CSV", "films.csv"),
        ("  RATINGS.CSV  ", "ratings.csv"),
        ("", ""),
    ],
)
def test_basename_lower(path, expected):
    assert _basename_lower(path) == expected


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("ratings.csv", "ratings.csv"),
        ("folder/ratings.csv", "ratings.csv"),
        ("diary.csv", "diary.csv"),
        ("watchlist.csv", "watchlist.csv"),
        ("watched.csv", "watched.csv"),
        ("likes/films.csv", "liked_films.csv"),
        ("LIKES/FILMS.CSV", "liked_films.csv"),
    ],
)
def test_match_canonical(path, expected):
    assert _match_canonical(path) == expected


@pytest.mark.parametrize("path", ["movies.csv", "likes/people.csv", "ratings.txt", ""])
def test_match_canonical_unknown(path):
    assert _match_canonical(path) is None


def test_decode_utf8():
    assert _decode("Amélie".encode("utf-8"), "test.csv") == "Amélie"


def test_decode_utf8_bom():
    assert _decode(b"\xef\xbb\xbfName,Year\n", "test.csv") == "Name,Year\n"


def test_decode_latin1():
    assert _decode("Amélie".encode("latin-1"), "test.csv") == "Amélie"


def test_parse_csv_text_returns_headers_and_rows():
    headers, rows = _parse_csv_text(
        "Name,Year,Rating\nAlien,1979,4.5\n", "ratings.csv"
    )
    assert headers == ["Name", "Year", "Rating"]
    assert rows == [{"Name": "Alien", "Year": "1979", "Rating": "4.5"}]


def test_parse_csv_text_preserves_extra_columns():
    headers, rows = _parse_csv_text(
        "Name,Year,Rating,Date\nAlien,1979,4.5,2026-01-01\n", "ratings.csv"
    )
    assert headers == ["Name", "Year", "Rating", "Date"]
    assert rows[0]["Date"] == "2026-01-01"


def test_parse_csv_text_rejects_empty_csv():
    with pytest.raises(LetterboxdImportError, match="empty or has no header row"):
        _parse_csv_text("", "ratings.csv")


def test_validate_columns_accepts_ratings():
    _validate_columns("ratings.csv", ["Name", "Year", "Rating"], "ratings.csv")


def test_validate_columns_accepts_extra_columns():
    _validate_columns(
        "ratings.csv", ["Name", "Year", "Rating", "Date", "Tags"], "ratings.csv"
    )


def test_validate_columns_accepts_unrestricted_canonical_file():
    _validate_columns("some_future_canonical.csv", ["Anything"], "whatever.csv")


@pytest.mark.parametrize(
    ("canonical", "fieldnames", "missing"),
    [
        ("ratings.csv", ["Name", "Year"], "Rating"),
        ("ratings.csv", ["Name", "Rating"], "Year"),
        ("ratings.csv", ["Year", "Rating"], "Name"),
        ("watchlist.csv", ["Name"], "Year"),
    ],
)
def test_validate_columns_rejects_missing_expected_columns(
    canonical, fieldnames, missing
):
    with pytest.raises(LetterboxdImportError, match=missing):
        _validate_columns(canonical, fieldnames, canonical)


def test_resolve_include_required_defaults():
    include, required = _resolve_include_and_required(None, None)
    assert include == ALL_CANONICAL
    assert required == set()


def test_resolve_include_required_returns_copies():
    include, required = _resolve_include_and_required(
        {"ratings.csv"}, {"ratings.csv"}
    )
    assert include == {"ratings.csv"}
    assert required == {"ratings.csv"}


@pytest.mark.parametrize(
    ("include", "required"),
    [({"unknown.csv"}, None), (None, {"unknown.csv"})],
)
def test_resolve_rejects_unknown_names(include, required):
    with pytest.raises(ValueError, match="Unknown canonical file name"):
        _resolve_include_and_required(include, required)


def test_resolve_rejects_required_not_in_include():
    with pytest.raises(ValueError, match="not present in 'include'"):
        _resolve_include_and_required({"ratings.csv"}, {"watchlist.csv"})



def test_extract_single_ratings_csv():
    raw = csv_bytes(
        ["Name", "Year", "Rating"],
        [{"Name": "Alien", "Year": "1979", "Rating": "4.5"}],
    )

    result = extract_letterboxd_csvs(
        (io.BytesIO(raw), "ratings.csv"),
        include={"ratings.csv"},
        required={"ratings.csv"},
    )

    assert isinstance(result, ExtractionResult)
    assert result.csvs == {
        "ratings.csv": [{"Name": "Alien", "Year": "1979", "Rating": "4.5"}]
    }
    assert result.missing == []


def test_extract_multiple_standalone_csvs():
    ratings = csv_bytes(
        ["Name", "Year", "Rating"],
        [{"Name": "Alien", "Year": "1979", "Rating": "4.5"}],
    )
    watchlist = csv_bytes(
        ["Name", "Year"], [{"Name": "Arrival", "Year": "2016"}]
    )

    result = extract_letterboxd_csvs(
        [
            (io.BytesIO(ratings), "ratings.csv"),
            (io.BytesIO(watchlist), "watchlist.csv"),
        ],
        include={"ratings.csv", "watchlist.csv"},
        required={"ratings.csv"},
    )

    assert set(result.csvs) == {"ratings.csv", "watchlist.csv"}
    assert result.csvs["watchlist.csv"] == [{"Name": "Arrival", "Year": "2016"}]
    assert result.missing == []


def test_extract_uses_file_name_attribute():
    raw = csv_bytes(
        ["Name", "Year", "Rating"],
        [{"Name": "Dune", "Year": "2021", "Rating": "5"}],
    )
    upload = NamedBytesIO(raw, name="ratings.csv")

    result = extract_letterboxd_csvs(
        upload, include={"ratings.csv"}, required={"ratings.csv"}
    )

    assert result.csvs["ratings.csv"][0]["Name"] == "Dune"


def test_extract_tuple_form_supplies_filename():
    raw = csv_bytes(
        ["Name", "Year", "Rating"],
        [{"Name": "Heat", "Year": "1995", "Rating": "4"}],
    )

    result = extract_letterboxd_csvs(
        (io.BytesIO(raw), "ratings.csv"), include={"ratings.csv"}
    )

    assert result.csvs["ratings.csv"][0]["Name"] == "Heat"


def test_standalone_requires_filename():
    raw = csv_bytes(["Name", "Year", "Rating"])

    with pytest.raises(LetterboxdImportError, match="original filename"):
        extract_letterboxd_csvs(io.BytesIO(raw), include={"ratings.csv"})


def test_standalone_matching_is_case_insensitive():
    raw = csv_bytes(
        ["Name", "Year", "Rating"],
        [{"Name": "Alien", "Year": "1979", "Rating": "4.5"}],
    )

    result = extract_letterboxd_csvs(
        (io.BytesIO(raw), "RATINGS.CSV"),
        include={"ratings.csv"},
    )

    assert result.csvs["ratings.csv"][0]["Name"] == "Alien"


def test_standalone_rejects_unknown_filename():
    raw = csv_bytes(["Name", "Year"])

    with pytest.raises(LetterboxdImportError, match="not one of the expected CSVs"):
        extract_letterboxd_csvs((io.BytesIO(raw), "movies.csv"), include={"watchlist.csv"})


def test_standalone_rejects_filename_outside_include():
    raw = csv_bytes(["Name", "Year", "Rating"])

    with pytest.raises(LetterboxdImportError, match="isn't needed"):
        extract_letterboxd_csvs((io.BytesIO(raw), "ratings.csv"), include={"watchlist.csv"})


def test_standalone_rejects_duplicate_canonical_file():
    raw1 = csv_bytes(
        ["Name", "Year", "Rating"],
        [{"Name": "Alien", "Year": "1979", "Rating": "4"}],
    )
    raw2 = csv_bytes(
        ["Name", "Year", "Rating"],
        [{"Name": "Heat", "Year": "1995", "Rating": "5"}],
    )

    with pytest.raises(LetterboxdImportError, match="duplicates"):
        extract_letterboxd_csvs(
            [
                (io.BytesIO(raw1), "ratings.csv"),
                (io.BytesIO(raw2), "folder/ratings.csv"),
            ],
            include={"ratings.csv"},
        )


def test_standalone_validates_ratings_header():
    raw = csv_bytes(["Name", "Year"], [{"Name": "Alien", "Year": "1979"}])

    with pytest.raises(LetterboxdImportError, match="missing expected column"):
        extract_letterboxd_csvs((io.BytesIO(raw), "ratings.csv"), include={"ratings.csv"})


def test_standalone_validates_watchlist_header():
    raw = csv_bytes(["Name"], [{"Name": "Arrival"}])

    with pytest.raises(LetterboxdImportError, match="Year"):
        extract_letterboxd_csvs(
            (io.BytesIO(raw), "watchlist.csv"), include={"watchlist.csv"}
        )


def test_standalone_supports_utf8_bom():
    raw = csv_bytes(
        ["Name", "Year", "Rating"],
        [{"Name": "Amélie", "Year": "2001", "Rating": "4.5"}],
        bom=True,
    )

    result = extract_letterboxd_csvs(
        (io.BytesIO(raw), "ratings.csv"), include={"ratings.csv"}
    )

    assert result.csvs["ratings.csv"][0]["Name"] == "Amélie"


def test_standalone_supports_latin1():
    raw = csv_bytes(
        ["Name", "Year", "Rating"],
        [{"Name": "Amélie", "Year": "2001", "Rating": "4.5"}],
        encoding="latin-1",
    )

    result = extract_letterboxd_csvs(
        (io.BytesIO(raw), "ratings.csv"), include={"ratings.csv"}
    )

    assert result.csvs["ratings.csv"][0]["Name"] == "Amélie"


def test_missing_contains_included_files_not_found():
    raw = csv_bytes(
        ["Name", "Year", "Rating"],
        [{"Name": "Alien", "Year": "1979", "Rating": "4.5"}],
    )

    result = extract_letterboxd_csvs(
        (io.BytesIO(raw), "ratings.csv"),
        include={"ratings.csv", "watchlist.csv"},
    )

    assert set(result.csvs) == {"ratings.csv"}
    assert set(result.missing) == {"watchlist.csv"}


def test_required_missing_raises():
    raw = csv_bytes(
        ["Name", "Year", "Rating"],
        [{"Name": "Alien", "Year": "1979", "Rating": "4.5"}],
    )

    with pytest.raises(LetterboxdImportError, match="missing the required CSV"):
        extract_letterboxd_csvs(
            (io.BytesIO(raw), "ratings.csv"),
            include={"ratings.csv", "watchlist.csv"},
            required={"watchlist.csv"},
        )


def test_empty_upload_list_raises():
    with pytest.raises(LetterboxdImportError, match="No files were uploaded"):
        extract_letterboxd_csvs([], include={"ratings.csv"})



def test_extract_single_csv_from_zip():
    ratings = csv_bytes(
        ["Name", "Year", "Rating"],
        [{"Name": "Alien", "Year": "1979", "Rating": "4.5"}],
    )
    archive = zip_bytes({"ratings.csv": ratings})

    result = extract_letterboxd_csvs(
        (io.BytesIO(archive), "export.zip"),
        include={"ratings.csv"},
        required={"ratings.csv"},
    )

    assert result.csvs["ratings.csv"] == [
        {"Name": "Alien", "Year": "1979", "Rating": "4.5"}
    ]
    assert result.missing == []


def test_extract_all_canonical_files_from_zip():
    files = {
        "ratings.csv": csv_bytes(
            ["Name", "Year", "Rating"],
            [{"Name": "Alien", "Year": "1979", "Rating": "4.5"}],
        ),
        "diary.csv": csv_bytes(
            ["Name", "Year", "Rating", "Watched Date"],
            [{"Name": "Arrival", "Year": "2016", "Rating": "4", "Watched Date": "2026-01-01"}],
        ),
        "watchlist.csv": csv_bytes(["Name", "Year"], [{"Name": "Dune", "Year": "2021"}]),
        "watched.csv": csv_bytes(["Name", "Year"], [{"Name": "Heat", "Year": "1995"}]),
        "likes/films.csv": csv_bytes(
            ["Name", "Year"], [{"Name": "The Matrix", "Year": "1999"}]
        ),
    }

    result = extract_letterboxd_csvs(
        (io.BytesIO(zip_bytes(files)), "export.zip"), include=ALL_CANONICAL
    )

    assert set(result.csvs) == ALL_CANONICAL
    assert result.csvs["liked_films.csv"] == [{"Name": "The Matrix", "Year": "1999"}]
    assert result.missing == []


def test_zip_matches_nested_canonical_file():
    ratings = csv_bytes(
        ["Name", "Year", "Rating"],
        [{"Name": "Alien", "Year": "1979", "Rating": "4.5"}],
    )
    archive = zip_bytes({"some/nested/ratings.csv": ratings})

    result = extract_letterboxd_csvs(
        (io.BytesIO(archive), "export.zip"), include={"ratings.csv"}
    )

    assert "ratings.csv" in result.csvs


def test_zip_extracts_liked_films():
    liked = csv_bytes(["Name", "Year"], [{"Name": "The Matrix", "Year": "1999"}])
    archive = zip_bytes({"likes/films.csv": liked})

    result = extract_letterboxd_csvs(
        (io.BytesIO(archive), "export.zip"), include={"liked_films.csv"}
    )

    assert result.csvs["liked_films.csv"] == [{"Name": "The Matrix", "Year": "1999"}]


def test_zip_ignores_files_not_in_include():
    ratings = csv_bytes(
        ["Name", "Year", "Rating"],
        [{"Name": "Alien", "Year": "1979", "Rating": "4.5"}],
    )
    archive = zip_bytes({"ratings.csv": ratings, "comments.csv": b"irrelevant"})

    result = extract_letterboxd_csvs(
        (io.BytesIO(archive), "export.zip"), include={"ratings.csv"}
    )

    assert set(result.csvs) == {"ratings.csv"}


def test_zip_ignores_duplicate_canonical_entries_after_first_match():
    first = csv_bytes(
        ["Name", "Year", "Rating"],
        [{"Name": "Alien", "Year": "1979", "Rating": "4.5"}],
    )
    second = csv_bytes(
        ["Name", "Year", "Rating"],
        [{"Name": "Heat", "Year": "1995", "Rating": "5"}],
    )
    archive = zip_bytes({"ratings.csv": first, "nested/ratings.csv": second})

    result = extract_letterboxd_csvs(
        (io.BytesIO(archive), "export.zip"), include={"ratings.csv"}
    )

    assert result.csvs["ratings.csv"] == [
        {"Name": "Alien", "Year": "1979", "Rating": "4.5"}
    ]


def test_corrupt_zip_raises():
    with pytest.raises(LetterboxdImportError, match=r"not a valid \.zip or is corrupted"):
        extract_letterboxd_csvs(
            (io.BytesIO(b"this is not a zip"), "export.zip"),
            include={"ratings.csv"},
        )


def test_zip_detected_by_magic_bytes_without_zip_extension():
    ratings = csv_bytes(
        ["Name", "Year", "Rating"],
        [{"Name": "Alien", "Year": "1979", "Rating": "4.5"}],
    )
    archive = zip_bytes({"ratings.csv": ratings})

    result = extract_letterboxd_csvs(
        (io.BytesIO(archive), "data.bin"), include={"ratings.csv"}
    )

    assert result.csvs["ratings.csv"][0]["Name"] == "Alien"


def test_zip_invalid_header_raises():
    ratings = csv_bytes(["Name", "Year"], [{"Name": "Alien", "Year": "1979"}])
    archive = zip_bytes({"ratings.csv": ratings})

    with pytest.raises(LetterboxdImportError, match="missing expected column"):
        extract_letterboxd_csvs(
            (io.BytesIO(archive), "export.zip"), include={"ratings.csv"}
        )


def test_zip_required_missing_raises():
    diary = csv_bytes(
        ["Name", "Year", "Rating", "Watched Date"],
        [{"Name": "Alien", "Year": "1979", "Rating": "4", "Watched Date": "2026-01-01"}],
    )
    archive = zip_bytes({"diary.csv": diary})

    with pytest.raises(LetterboxdImportError, match="missing the required CSV"):
        extract_letterboxd_csvs(
            (io.BytesIO(archive), "export.zip"),
            include={"diary.csv", "ratings.csv"},
            required={"ratings.csv"},
        )


def test_zip_missing_reports_included_files_not_found():
    diary = csv_bytes(
        ["Name", "Year", "Rating", "Watched Date"],
        [{"Name": "Alien", "Year": "1979", "Rating": "4", "Watched Date": "2026-01-01"}],
    )
    archive = zip_bytes({"diary.csv": diary})

    result = extract_letterboxd_csvs(
        (io.BytesIO(archive), "export.zip"),
        include={"diary.csv", "ratings.csv"},
    )

    assert set(result.csvs) == {"diary.csv"}
    assert set(result.missing) == {"ratings.csv"}


def test_mixed_zip_and_standalone_uploads_are_rejected():
    ratings = csv_bytes(
        ["Name", "Year", "Rating"],
        [{"Name": "Alien", "Year": "1979", "Rating": "4.5"}],
    )
    archive = zip_bytes({"ratings.csv": ratings})
    diary = csv_bytes(["Name"], [{"Name": "Arrival"}])

    with pytest.raises(LetterboxdImportError, match="zip archive"):
        extract_letterboxd_csvs(
            [
                (io.BytesIO(archive), "export.zip"),
                (io.BytesIO(diary), "diary.csv"),
            ],
            include={"ratings.csv", "diary.csv"},
        )


def test_empty_zip_returns_all_included_files_as_missing():
    archive = zip_bytes({"README.txt": b"nothing useful"})

    result = extract_letterboxd_csvs(
        (io.BytesIO(archive), "export.zip"),
        include={"ratings.csv", "watchlist.csv"},
    )

    assert result.csvs == {}
    assert set(result.missing) == {"ratings.csv", "watchlist.csv"}


def test_empty_zip_with_required_file_raises():
    archive = zip_bytes({"README.txt": b"nothing useful"})

    with pytest.raises(
        LetterboxdImportError,
        match="missing the required CSV",
    ):
        extract_letterboxd_csvs(
            (io.BytesIO(archive), "export.zip"),
            include={"ratings.csv"},
            required={"ratings.csv"},
        )



def test_list_of_two_bare_uploads_is_treated_as_multiple_files():
    ratings = NamedBytesIO(
        csv_bytes(
            ["Name", "Year", "Rating"],
            [{"Name": "Alien", "Year": "1979", "Rating": "4.5"}],
        ),
        name="ratings.csv",
    )
    watchlist = NamedBytesIO(
        csv_bytes(["Name", "Year"], [{"Name": "Arrival", "Year": "2016"}]),
        name="watchlist.csv",
    )

    result = extract_letterboxd_csvs(
        [ratings, watchlist],
        include={"ratings.csv", "watchlist.csv"},
    )

    assert set(result.csvs) == {"ratings.csv", "watchlist.csv"}
    assert result.csvs["ratings.csv"][0]["Name"] == "Alien"
    assert result.csvs["watchlist.csv"][0]["Name"] == "Arrival"


def test_list_of_two_bare_uploads_without_filename_raises_expected_error():
    raw1 = csv_bytes(["Name", "Year", "Rating"])
    raw2 = csv_bytes(["Name", "Year"])

    with pytest.raises(LetterboxdImportError, match="original filename"):
        extract_letterboxd_csvs(
            [io.BytesIO(raw1), io.BytesIO(raw2)],
            include={"ratings.csv", "watchlist.csv"},
        )


def test_list_of_two_bare_zip_uploads_is_rejected_as_mixed():
    archive1 = zip_bytes({"ratings.csv": csv_bytes(["Name", "Year", "Rating"])})
    archive2 = zip_bytes({"diary.csv": csv_bytes(["Name"])})

    upload1 = NamedBytesIO(archive1, name="export1.zip")
    upload2 = NamedBytesIO(archive2, name="export2.zip")

    with pytest.raises(LetterboxdImportError, match="zip archive"):
        extract_letterboxd_csvs(
            [upload1, upload2],
            include={"ratings.csv", "diary.csv"},
        )


def test_single_item_list_containing_a_tuple_behaves_like_bare_tuple():
    raw = csv_bytes(
        ["Name", "Year", "Rating"],
        [{"Name": "Heat", "Year": "1995", "Rating": "4"}],
    )

    result = extract_letterboxd_csvs(
        [(io.BytesIO(raw), "ratings.csv")],
        include={"ratings.csv"},
    )

    assert result.csvs["ratings.csv"][0]["Name"] == "Heat"


def test_single_item_list_containing_a_zip_tuple_is_detected_as_zip():
    ratings = csv_bytes(
        ["Name", "Year", "Rating"],
        [{"Name": "Alien", "Year": "1979", "Rating": "4.5"}],
    )
    archive = zip_bytes({"ratings.csv": ratings})

    result = extract_letterboxd_csvs(
        [(io.BytesIO(archive), "export.zip")],
        include={"ratings.csv"},
    )

    assert result.csvs["ratings.csv"][0]["Name"] == "Alien"


def test_tuple_form_with_none_filename_still_requires_filename():
    raw = csv_bytes(["Name", "Year", "Rating"])

    with pytest.raises(LetterboxdImportError, match="original filename"):
        extract_letterboxd_csvs((io.BytesIO(raw), None), include={"ratings.csv"})



def test_default_include_means_every_canonical_file_is_eligible():
    ratings = csv_bytes(
        ["Name", "Year", "Rating"],
        [{"Name": "Alien", "Year": "1979", "Rating": "4.5"}],
    )

    result = extract_letterboxd_csvs((io.BytesIO(ratings), "ratings.csv"))

    assert set(result.csvs) == {"ratings.csv"}
    assert set(result.missing) == ALL_CANONICAL - {"ratings.csv"}


def test_include_only_rejects_unrequested_file():
    ratings = csv_bytes(
        ["Name", "Year", "Rating"],
        [{"Name": "Alien", "Year": "1979", "Rating": "4.5"}],
    )
    watchlist = csv_bytes(
        ["Name", "Year"],
        [{"Name": "Dune", "Year": "2021"}],
    )

    with pytest.raises(
        LetterboxdImportError,
        match="isn't needed for this import and was rejected",
    ):
        extract_letterboxd_csvs(
            [
                (io.BytesIO(ratings), "ratings.csv"),
                (io.BytesIO(watchlist), "watchlist.csv"),
            ],
            include={"ratings.csv"},
        )


def test_required_must_be_subset_of_include_through_public_api():
    with pytest.raises(ValueError, match="not present in 'include'"):
        extract_letterboxd_csvs(
            (io.BytesIO(b""), "ratings.csv"),
            include={"ratings.csv"},
            required={"watchlist.csv"},
        )


def test_csv_values_are_returned_as_strings():
    raw = csv_bytes(
        ["Name", "Year", "Rating"],
        [{"Name": "Alien", "Year": "1979", "Rating": "4.5"}],
    )

    result = extract_letterboxd_csvs(
        (io.BytesIO(raw), "ratings.csv"), include={"ratings.csv"}
    )

    row = result.csvs["ratings.csv"][0]
    assert all(isinstance(value, str) for value in row.values())


def test_empty_csv_with_header_is_valid_and_returns_no_rows():
    raw = csv_bytes(["Name", "Year", "Rating"])

    result = extract_letterboxd_csvs(
        (io.BytesIO(raw), "ratings.csv"), include={"ratings.csv"}
    )

    assert result.csvs["ratings.csv"] == []


def test_standalone_non_utf8_binary_is_decoded_by_latin1_fallback():
    raw = b"Name,Year,Rating\nMovie,2020,4.0\n\xff"

    result = extract_letterboxd_csvs(
        (io.BytesIO(raw), "ratings.csv"), include={"ratings.csv"}
    )

    assert result.csvs["ratings.csv"][0]["Name"] == "Movie"
