from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.comparisons.services.snapshot import (
    RatedFilm,
    UserLibrary,
    compute_inputs_hash,
    film_key,
)
from apps.comparisons.services.snapshot import load_library
from apps.movies.models import Movie
from apps.library.models import Rating

User = get_user_model()


class FilmKeyTests(TestCase):
    def test_strips_and_casefolds_title(self):
        self.assertEqual(
            film_key("  The Matrix  ", 1999),
            ("the matrix", 1999),
        )

    def test_preserves_release_year(self):
        self.assertEqual(
            film_key("Dune", 2021),
            ("dune", 2021),
        )

    def test_allows_none_release_year(self):
        self.assertEqual(
            film_key("Unknown", None),
            ("unknown", None),
        )

    def test_casefolds_unicode(self):
        self.assertEqual(
            film_key("Straße", 2020),
            film_key("STRASSE", 2020),
        )


class RatedFilmTests(TestCase):
    def test_defaults(self):
        film = RatedFilm(
            title="Dune",
            release_year=2021,
            rating=4.5,
            liked=True,
        )

        self.assertEqual(film.movie_id, None)
        self.assertEqual(film.genres, frozenset())
        self.assertEqual(film.directors, ())

    def test_is_frozen(self):
        film = RatedFilm(
            title="Dune",
            release_year=2021,
            rating=4.5,
            liked=True,
        )

        with self.assertRaises(AttributeError):
            film.title = "Alien"


class UserLibraryTests(TestCase):
    def test_defaults_to_empty_films(self):
        library = UserLibrary(user_id=1)

        self.assertEqual(library.user_id, 1)
        self.assertEqual(library.films, {})

    def test_films_dict_is_not_shared(self):
        first = UserLibrary(user_id=1)
        second = UserLibrary(user_id=2)

        first.films[("dune", 2021)] = RatedFilm(
            title="Dune",
            release_year=2021,
            rating=5.0,
            liked=True,
        )

        self.assertEqual(second.films, {})


class LoadLibraryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="a@x.com",
            username="a",
            password="pw",
        )

    def test_returns_user_library(self):
        Rating.objects.create(
            user=self.user,
            title="Dune",
            release_year=2021,
            rating=5.0,
            liked=True,
        )

        result = load_library(self.user)

        self.assertIsInstance(result, UserLibrary)
        self.assertEqual(result.user_id, self.user.pk)
        self.assertEqual(len(result.films), 1)

    def test_maps_rating_fields(self):
        Rating.objects.create(
            user=self.user,
            title="Dune",
            release_year=2021,
            rating=4.5,
            liked=True,
        )

        result = load_library(self.user)
        film = result.films[("dune", 2021)]

        self.assertEqual(film.title, "Dune")
        self.assertEqual(film.release_year, 2021)
        self.assertEqual(film.rating, 4.5)
        self.assertTrue(film.liked)
        self.assertIsNone(film.movie_id)

    def test_normalizes_film_key(self):
        Rating.objects.create(
            user=self.user,
            title="  DUNE  ",
            release_year=2021,
            rating=4.0,
            liked=False,
        )

        result = load_library(self.user)

        self.assertIn(
            ("dune", 2021),
            result.films,
        )

    def test_uses_movie_id(self):
        movie = Movie.objects.create(
            tmdb_id=1001,
            title="Dune",
            release_year=2021,
        )

        Rating.objects.create(
            user=self.user,
            title="Dune",
            release_year=2021,
            rating=5.0,
            liked=True,
            movie=movie,
        )

        result = load_library(self.user)
        film = result.films[("dune", 2021)]

        self.assertEqual(
            film.movie_id,
            movie.pk,
        )

    def test_extracts_genres(self):
        from apps.movies.models import Genre

        movie = Movie.objects.create(
            tmdb_id=1002,
            title="Dune",
            release_year=2021,
        )

        action = Genre.objects.create(
            name="Action",
        )
        science_fiction = Genre.objects.create(
            name="Science Fiction",
        )

        movie.genres.add(
            action,
            science_fiction,
        )

        Rating.objects.create(
            user=self.user,
            title="Dune",
            release_year=2021,
            rating=5.0,
            liked=True,
            movie=movie,
        )

        result = load_library(self.user)
        film = result.films[("dune", 2021)]

        self.assertEqual(
            film.genres,
            frozenset({
                "Action",
                "Science Fiction",
            }),
        )

    def test_extracts_only_string_directors(self):
        movie = Movie.objects.create(
            tmdb_id=1003,
            title="Dune",
            release_year=2021,
            directors=[
                "Denis Villeneuve",
                123,
                None,
                "Christopher Nolan",
            ],
        )

        Rating.objects.create(
            user=self.user,
            title="Dune",
            release_year=2021,
            rating=5.0,
            liked=True,
            movie=movie,
        )

        result = load_library(self.user)
        film = result.films[("dune", 2021)]

        self.assertEqual(
            film.directors,
            (
                "Denis Villeneuve",
                "Christopher Nolan",
            ),
        )

    def test_handles_movie_without_genres_or_directors(self):
        movie = Movie.objects.create(
            tmdb_id=1004,
            title="Dune",
            release_year=2021,
            directors=None,
        )

        Rating.objects.create(
            user=self.user,
            title="Dune",
            release_year=2021,
            rating=5.0,
            liked=True,
            movie=movie,
        )

        result = load_library(self.user)
        film = result.films[("dune", 2021)]

        self.assertEqual(film.genres, frozenset())
        self.assertEqual(film.directors, ())

    def test_handles_rating_without_movie(self):
        Rating.objects.create(
            user=self.user,
            title="Unknown",
            release_year=None,
            rating=3.0,
            liked=False,
            movie=None,
        )

        result = load_library(self.user)
        film = result.films[("unknown", None)]

        self.assertIsNone(film.movie_id)
        self.assertEqual(film.genres, frozenset())
        self.assertEqual(film.directors, ())

    def test_duplicate_film_key_is_overwritten_by_last_rating(self):
        Rating.objects.create(
            user=self.user,
            title="Dune",
            release_year=2021,
            rating=3.0,
            liked=False,
        )
        Rating.objects.create(
            user=self.user,
            title="  dune ",
            release_year=2021,
            rating=5.0,
            liked=True,
        )

        result = load_library(self.user)

        self.assertEqual(len(result.films), 1)
        self.assertEqual(
            result.films[("dune", 2021)].rating,
            5.0,
        )
        self.assertTrue(
            result.films[("dune", 2021)].liked,
        )


class ComputeInputsHashTests(TestCase):
    def _film(
        self,
        title="Dune",
        release_year=2021,
        rating=4.5,
        liked=True,
    ):
        return RatedFilm(
            title=title,
            release_year=release_year,
            rating=rating,
            liked=liked,
        )

    def test_returns_sha256_hex_digest(self):
        library = UserLibrary(
            user_id=1,
            films={
                ("dune", 2021): self._film(),
            },
        )

        result = compute_inputs_hash([library])

        self.assertEqual(len(result), 64)
        self.assertRegex(result, r"^[0-9a-f]{64}$")

    def test_is_deterministic(self):
        library = UserLibrary(
            user_id=1,
            films={
                ("dune", 2021): self._film(),
            },
        )

        self.assertEqual(
            compute_inputs_hash([library]),
            compute_inputs_hash([library]),
        )

    def test_different_rating_changes_hash(self):
        first = UserLibrary(
            user_id=1,
            films={
                ("dune", 2021): self._film(rating=4.0),
            },
        )
        second = UserLibrary(
            user_id=1,
            films={
                ("dune", 2021): self._film(rating=5.0),
            },
        )

        self.assertNotEqual(
            compute_inputs_hash([first]),
            compute_inputs_hash([second]),
        )

    def test_different_liked_value_changes_hash(self):
        first = UserLibrary(
            user_id=1,
            films={
                ("dune", 2021): self._film(liked=False),
            },
        )
        second = UserLibrary(
            user_id=1,
            films={
                ("dune", 2021): self._film(liked=True),
            },
        )

        self.assertNotEqual(
            compute_inputs_hash([first]),
            compute_inputs_hash([second]),
        )

    def test_different_release_year_changes_hash(self):
        first = UserLibrary(
            user_id=1,
            films={
                ("dune", 2020): self._film(release_year=2020),
            },
        )
        second = UserLibrary(
            user_id=1,
            films={
                ("dune", 2021): self._film(release_year=2021),
            },
        )

        self.assertNotEqual(
            compute_inputs_hash([first]),
            compute_inputs_hash([second]),
        )

    def test_different_title_changes_hash(self):
        first = UserLibrary(
            user_id=1,
            films={
                ("dune", 2021): self._film(title="Dune"),
            },
        )
        second = UserLibrary(
            user_id=1,
            films={
                ("dune", 2021): self._film(title="Dune Part One"),
            },
        )

        self.assertNotEqual(
            compute_inputs_hash([first]),
            compute_inputs_hash([second]),
        )

    def test_different_user_id_changes_hash(self):
        first = UserLibrary(
            user_id=1,
            films={
                ("dune", 2021): self._film(),
            },
        )
        second = UserLibrary(
            user_id=2,
            films={
                ("dune", 2021): self._film(),
            },
        )

        self.assertNotEqual(
            compute_inputs_hash([first]),
            compute_inputs_hash([second]),
        )

    def test_film_order_does_not_change_hash(self):
        first = UserLibrary(
            user_id=1,
            films={
                ("dune", 2021): self._film(),
                ("alien", 1979): self._film(
                    title="Alien",
                    release_year=1979,
                ),
            },
        )
        second = UserLibrary(
            user_id=1,
            films={
                ("alien", 1979): self._film(
                    title="Alien",
                    release_year=1979,
                ),
                ("dune", 2021): self._film(),
            },
        )

        self.assertEqual(
            compute_inputs_hash([first]),
            compute_inputs_hash([second]),
        )

    def test_library_order_does_not_change_hash(self):
        first = UserLibrary(
            user_id=1,
            films={
                ("dune", 2021): self._film(),
            },
        )
        second = UserLibrary(
            user_id=2,
            films={
                ("alien", 1979): self._film(
                    title="Alien",
                    release_year=1979,
                ),
            },
        )

        self.assertEqual(
            compute_inputs_hash([first, second]),
            compute_inputs_hash([second, first]),
        )

    def test_movie_id_does_not_affect_hash(self):
        first = UserLibrary(
            user_id=1,
            films={
                ("dune", 2021): RatedFilm(
                    title="Dune",
                    release_year=2021,
                    rating=5.0,
                    liked=True,
                    movie_id=10,
                ),
            },
        )
        second = UserLibrary(
            user_id=1,
            films={
                ("dune", 2021): RatedFilm(
                    title="Dune",
                    release_year=2021,
                    rating=5.0,
                    liked=True,
                    movie_id=20,
                ),
            },
        )

        self.assertEqual(
            compute_inputs_hash([first]),
            compute_inputs_hash([second]),
        )

    def test_genres_and_directors_do_not_affect_hash(self):
        first = UserLibrary(
            user_id=1,
            films={
                ("dune", 2021): RatedFilm(
                    title="Dune",
                    release_year=2021,
                    rating=5.0,
                    liked=True,
                    genres=frozenset({"Sci-Fi"}),
                    directors=("Denis Villeneuve",),
                ),
            },
        )
        second = UserLibrary(
            user_id=1,
            films={
                ("dune", 2021): RatedFilm(
                    title="Dune",
                    release_year=2021,
                    rating=5.0,
                    liked=True,
                    genres=frozenset({"Drama"}),
                    directors=("Christopher Nolan",),
                ),
            },
        )

        self.assertEqual(
            compute_inputs_hash([first]),
            compute_inputs_hash([second]),
        )

    def test_empty_libraries_are_deterministic(self):
        self.assertEqual(
            compute_inputs_hash([]),
            compute_inputs_hash([]),
        )
