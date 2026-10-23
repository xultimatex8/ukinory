from __future__ import annotations

import pytest

from apps.library.services.keys import film_key


@pytest.mark.parametrize(
    ("title", "year", "expected"),
    [
        ("The Matrix", 1999, ("the matrix", 1999)),
        ("  The Matrix  ", 1999, ("the matrix", 1999)),
        ("\tDune\n", 2021, ("dune", 2021)),
        ("DUNE", 2021, ("dune", 2021)),
        ("Unknown", None, ("unknown", None)),
        ("   ", 2000, ("", 2000)),
        ("", None, ("", None)),
    ],
)
def test_film_key(title, year, expected):
    assert film_key(title, year) == expected


def test_internal_whitespace_is_preserved():
    assert film_key("Blade  Runner", 1982) == ("blade  runner", 1982)


def test_casefold_matches_unicode_variants():
    assert film_key("Straße", 2020) == film_key("STRASSE", 2020)


def test_different_years_give_different_keys():
    assert film_key("Dune", 1984) != film_key("Dune", 2021)


def test_missing_year_differs_from_any_year():
    assert film_key("Dune", None) != film_key("Dune", 2021)


def test_equivalent_titles_collapse_to_the_same_dict_key():
    films = {film_key("Dune", 2021): "first"}
    films[film_key("  dune ", 2021)] = "second"

    assert films == {("dune", 2021): "second"}


def test_returns_a_tuple():
    assert isinstance(film_key("Dune", 2021), tuple)
