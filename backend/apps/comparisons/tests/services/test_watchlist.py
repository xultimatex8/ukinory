from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.common.enums import SessionType, WatchlistSource
from apps.comparisons.exceptions import (
    RecommendationNotFoundError,
    RoomNotReadyError,
)
from apps.comparisons.models import (
    Comparison,
    ComparisonNarrative,
    ComparisonSession,
)
from apps.comparisons.services.watchlist import (
    add_recommendation_to_watchlist,
    attach_watchlist_state,
    export_recommendations_csv,
    remove_recommendation_from_watchlist,
)
from apps.library.models import WatchlistEntry
from apps.movies.models import Movie

User = get_user_model()

INPUTS_HASH = "hash-1"


class WatchlistServiceTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="a@x.com", username="a", password="pw"
        )
        self.other = User.objects.create_user(
            email="b@x.com", username="b", password="pw"
        )

        self.dune = Movie.objects.create(
            tmdb_id=2001, title="Dune", release_year=2021
        )
        self.alien = Movie.objects.create(
            tmdb_id=2002, title="Alien", release_year=1979
        )
        self.heat = Movie.objects.create(
            tmdb_id=2003, title="Heat", release_year=1995
        )

        self.room_id = self._create_room(with_comparison=True).pk
        self.set_recommendations([self.dune, self.alien])

    def _create_room(self, *, with_comparison: bool) -> ComparisonSession:
        room = ComparisonSession.objects.create(
            session_type=SessionType.COMPARISON_SESSION
        )
        room.users.add(self.user, self.other)
        if with_comparison:
            Comparison.objects.create(session=room, inputs_hash=INPUTS_HASH)
        return room

    def fresh_room(self) -> ComparisonSession:
        return ComparisonSession.objects.get(pk=self.room_id)

    def set_recommendations(self, movies, inputs_hash=INPUTS_HASH):
        comparison = Comparison.objects.get(session_id=self.room_id)
        ComparisonNarrative.objects.update_or_create(
            comparison=comparison,
            inputs_hash=inputs_hash,
            defaults={
                "narrative_summary": "summary",
                "individual_summaries": {},
                "recommendations": [
                    {"movie_id": str(m.pk), "title": m.title} for m in movies
                ],
                "model_version": "test",
            },
        )

    def watchlist(self, user=None):
        return WatchlistEntry.objects.filter(user=user or self.user)


class ReadinessTests(WatchlistServiceTestCase):
    def test_add_raises_not_ready_when_room_has_no_comparison(self):
        room = self._create_room(with_comparison=False)
        room = ComparisonSession.objects.get(pk=room.pk)

        with self.assertRaises(RoomNotReadyError):
            add_recommendation_to_watchlist(
                room=room, user=self.user, movie_id=self.dune.pk
            )

    def test_add_raises_not_ready_when_no_narrative_for_current_hash(self):
        Comparison.objects.filter(session_id=self.room_id).update(
            inputs_hash="changed"
        )

        with self.assertRaises(RoomNotReadyError):
            add_recommendation_to_watchlist(
                room=self.fresh_room(), user=self.user, movie_id=self.dune.pk
            )

    def test_stale_narrative_recommendations_are_ignored(self):
        self.set_recommendations([self.heat], inputs_hash="old-hash")

        with self.assertRaises(RecommendationNotFoundError):
            add_recommendation_to_watchlist(
                room=self.fresh_room(), user=self.user, movie_id=self.heat.pk
            )

    def test_export_raises_not_ready_when_room_has_no_comparison(self):
        room = self._create_room(with_comparison=False)
        room = ComparisonSession.objects.get(pk=room.pk)

        with self.assertRaises(RoomNotReadyError):
            export_recommendations_csv(room=room, user=self.user)


class AddRecommendationTests(WatchlistServiceTestCase):
    def test_creates_watchlist_entry(self):
        add_recommendation_to_watchlist(
            room=self.fresh_room(), user=self.user, movie_id=self.dune.pk
        )

        entry = self.watchlist().get()
        self.assertEqual(entry.title, "Dune")
        self.assertEqual(entry.release_year, 2021)
        self.assertEqual(entry.movie_id, self.dune.pk)
        self.assertEqual(entry.source, WatchlistSource.COMPARISON_ADDED)
        self.assertEqual(entry.added_date, timezone.localdate())

    def test_accepts_movie_id_as_string(self):
        add_recommendation_to_watchlist(
            room=self.fresh_room(),
            user=self.user,
            movie_id=str(self.dune.pk),
        )

        self.assertEqual(self.watchlist().count(), 1)

    def test_is_idempotent(self):
        for _ in range(2):
            add_recommendation_to_watchlist(
                room=self.fresh_room(), user=self.user, movie_id=self.dune.pk
            )

        self.assertEqual(self.watchlist().count(), 1)

    def test_does_not_touch_other_users_watchlist(self):
        add_recommendation_to_watchlist(
            room=self.fresh_room(), user=self.user, movie_id=self.dune.pk
        )

        self.assertEqual(self.watchlist(self.other).count(), 0)

    def test_does_not_override_source_of_existing_entry(self):
        WatchlistEntry.objects.create(
            user=self.user,
            title="Dune",
            release_year=2021,
            source=WatchlistSource.IMPORTED,
            movie=self.dune,
        )

        add_recommendation_to_watchlist(
            room=self.fresh_room(), user=self.user, movie_id=self.dune.pk
        )

        entry = self.watchlist().get()
        self.assertEqual(entry.source, WatchlistSource.IMPORTED)

    def test_links_movie_on_existing_entry_without_movie(self):
        WatchlistEntry.objects.create(
            user=self.user,
            title="Dune",
            release_year=2021,
            source=WatchlistSource.IMPORTED,
            movie=None,
        )

        add_recommendation_to_watchlist(
            room=self.fresh_room(), user=self.user, movie_id=self.dune.pk
        )

        entry = self.watchlist().get()
        self.assertEqual(entry.movie_id, self.dune.pk)
        self.assertEqual(entry.source, WatchlistSource.IMPORTED)

    def test_rejects_movie_that_is_not_recommended(self):
        with self.assertRaises(RecommendationNotFoundError):
            add_recommendation_to_watchlist(
                room=self.fresh_room(), user=self.user, movie_id=self.heat.pk
            )

        self.assertEqual(self.watchlist().count(), 0)

    def test_rejects_unknown_movie_id(self):
        with self.assertRaises(RecommendationNotFoundError):
            add_recommendation_to_watchlist(
                room=self.fresh_room(), user=self.user, movie_id="999999"
            )


class RemoveRecommendationTests(WatchlistServiceTestCase):
    def test_removes_entry(self):
        add_recommendation_to_watchlist(
            room=self.fresh_room(), user=self.user, movie_id=self.dune.pk
        )

        remove_recommendation_from_watchlist(
            room=self.fresh_room(), user=self.user, movie_id=self.dune.pk
        )

        self.assertEqual(self.watchlist().count(), 0)

    def test_removes_entry_matching_title_and_year_without_movie(self):
        WatchlistEntry.objects.create(
            user=self.user,
            title="Dune",
            release_year=2021,
            source=WatchlistSource.IMPORTED,
            movie=None,
        )

        remove_recommendation_from_watchlist(
            room=self.fresh_room(), user=self.user, movie_id=self.dune.pk
        )

        self.assertEqual(self.watchlist().count(), 0)

    def test_keeps_other_films_and_other_users_entries(self):
        for user in (self.user, self.other):
            add_recommendation_to_watchlist(
                room=self.fresh_room(), user=user, movie_id=self.dune.pk
            )
        add_recommendation_to_watchlist(
            room=self.fresh_room(), user=self.user, movie_id=self.alien.pk
        )

        remove_recommendation_from_watchlist(
            room=self.fresh_room(), user=self.user, movie_id=self.dune.pk
        )

        self.assertEqual(
            list(self.watchlist().values_list("title", flat=True)),
            ["Alien"],
        )
        self.assertEqual(self.watchlist(self.other).count(), 1)

    def test_is_noop_when_entry_does_not_exist(self):
        remove_recommendation_from_watchlist(
            room=self.fresh_room(), user=self.user, movie_id=self.dune.pk
        )

        self.assertEqual(self.watchlist().count(), 0)

    def test_rejects_movie_that_is_not_recommended(self):
        with self.assertRaises(RecommendationNotFoundError):
            remove_recommendation_from_watchlist(
                room=self.fresh_room(), user=self.user, movie_id=self.heat.pk
            )


class AttachWatchlistStateTests(WatchlistServiceTestCase):
    def _payload(self):
        return {
            "metrics": {"compatibility_score": 80},
            "recommendations": [
                {"movie_id": str(self.dune.pk), "title": "Dune"},
                {"movie_id": str(self.alien.pk), "title": "Alien"},
            ],
        }

    def _flags(self, payload):
        return {
            r["title"]: r["in_watchlist"] for r in payload["recommendations"]
        }

    def test_flags_nothing_when_watchlist_is_empty(self):
        result = attach_watchlist_state(self._payload(), self.user)

        self.assertEqual(
            self._flags(result), {"Dune": False, "Alien": False}
        )

    def test_flags_entries_linked_to_the_movie(self):
        add_recommendation_to_watchlist(
            room=self.fresh_room(), user=self.user, movie_id=self.dune.pk
        )

        result = attach_watchlist_state(self._payload(), self.user)

        self.assertEqual(
            self._flags(result), {"Dune": True, "Alien": False}
        )

    def test_flags_entries_matched_by_title_and_year(self):
        WatchlistEntry.objects.create(
            user=self.user,
            title="Alien",
            release_year=1979,
            source=WatchlistSource.IMPORTED,
            movie=None,
        )

        result = attach_watchlist_state(self._payload(), self.user)

        self.assertEqual(
            self._flags(result), {"Dune": False, "Alien": True}
        )

    def test_same_title_with_different_year_is_not_a_match(self):
        WatchlistEntry.objects.create(
            user=self.user,
            title="Dune",
            release_year=1984,
            source=WatchlistSource.IMPORTED,
            movie=None,
        )

        result = attach_watchlist_state(self._payload(), self.user)

        self.assertFalse(self._flags(result)["Dune"])

    def test_ignores_other_users_entries(self):
        add_recommendation_to_watchlist(
            room=self.fresh_room(), user=self.other, movie_id=self.dune.pk
        )

        result = attach_watchlist_state(self._payload(), self.user)

        self.assertFalse(self._flags(result)["Dune"])

    def test_preserves_the_rest_of_the_payload_and_does_not_mutate_input(self):
        payload = self._payload()

        result = attach_watchlist_state(payload, self.user)

        self.assertEqual(result["metrics"], {"compatibility_score": 80})
        self.assertEqual(result["recommendations"][0]["title"], "Dune")
        self.assertNotIn("in_watchlist", payload["recommendations"][0])

    def test_handles_empty_and_missing_recommendations(self):
        self.assertEqual(
            attach_watchlist_state({"recommendations": []}, self.user)[
                "recommendations"
            ],
            [],
        )
        self.assertEqual(
            attach_watchlist_state({}, self.user)["recommendations"],
            [],
        )


class ExportRecommendationsCsvTests(WatchlistServiceTestCase):
    def _lines(self, content: str) -> list[str]:
        return content.splitlines()

    def test_returns_only_header_when_nothing_is_saved(self):
        content, count = export_recommendations_csv(
            room=self.fresh_room(), user=self.user
        )

        self.assertEqual(count, 0)
        self.assertEqual(self._lines(content), ["Title,Year"])

    def test_exports_only_saved_recommendations(self):
        add_recommendation_to_watchlist(
            room=self.fresh_room(), user=self.user, movie_id=self.alien.pk
        )

        content, count = export_recommendations_csv(
            room=self.fresh_room(), user=self.user
        )

        self.assertEqual(count, 1)
        self.assertEqual(
            self._lines(content), ["Title,Year", "Alien,1979"]
        )

    def test_follows_recommendation_order(self):
        self.set_recommendations([self.alien, self.dune])
        for movie in (self.dune, self.alien):
            add_recommendation_to_watchlist(
                room=self.fresh_room(), user=self.user, movie_id=movie.pk
            )

        content, count = export_recommendations_csv(
            room=self.fresh_room(), user=self.user
        )

        self.assertEqual(count, 2)
        self.assertEqual(
            self._lines(content),
            ["Title,Year", "Alien,1979", "Dune,2021"],
        )

    def test_leaves_year_blank_when_unknown(self):
        untitled = Movie.objects.create(
            tmdb_id=2004, title="Untitled", release_year=None
        )
        self.set_recommendations([untitled])
        add_recommendation_to_watchlist(
            room=self.fresh_room(), user=self.user, movie_id=untitled.pk
        )

        content, count = export_recommendations_csv(
            room=self.fresh_room(), user=self.user
        )

        self.assertEqual(count, 1)
        self.assertEqual(self._lines(content), ["Title,Year", "Untitled,"])

    def test_ignores_watchlist_films_that_were_not_recommended(self):
        WatchlistEntry.objects.create(
            user=self.user,
            title="Heat",
            release_year=1995,
            source=WatchlistSource.IMPORTED,
            movie=self.heat,
        )

        content, count = export_recommendations_csv(
            room=self.fresh_room(), user=self.user
        )

        self.assertEqual(count, 0)
        self.assertEqual(self._lines(content), ["Title,Year"])

    def test_ignores_other_users_entries(self):
        add_recommendation_to_watchlist(
            room=self.fresh_room(), user=self.other, movie_id=self.dune.pk
        )

        content, count = export_recommendations_csv(
            room=self.fresh_room(), user=self.user
        )

        self.assertEqual(count, 0)
        self.assertEqual(self._lines(content), ["Title,Year"])
