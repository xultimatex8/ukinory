from __future__ import annotations

import pytest

from apps.common.enums import SessionType
from apps.swipe_sessions.models import SwipeSession, SwipeSessionCandidate
from apps.swipe_sessions.services.cleanup import delete_orphaned_sessions
from apps.movies.models import Movie


@pytest.fixture
def movie(db):
    return Movie.objects.create(tmdb_id=438631, title="Dune", release_year=2021)



def make_session(*users):
    session = SwipeSession.objects.create(
        type="solo", session_type=SessionType.SWIPE_SESSION
    )
    session.users.add(*users)
    return session


@pytest.mark.django_db
class TestDeleteOrphanedSessions:
    def test_deletes_sessions_without_users(self):
        orphan = make_session()

        delete_orphaned_sessions()

        assert not SwipeSession.objects.filter(pk=orphan.pk).exists()

    def test_keeps_sessions_that_still_have_users(self, user, another_user):
        solo = make_session(user)
        shared = make_session(user, another_user)

        delete_orphaned_sessions()

        assert SwipeSession.objects.filter(pk=solo.pk).exists()
        assert SwipeSession.objects.filter(pk=shared.pk).exists()

    def test_returns_the_number_of_deleted_objects(self):
        make_session()
        make_session()

        deleted, per_model = delete_orphaned_sessions()

        assert deleted >= 2
        assert any(count >= 2 for count in per_model.values())

    def test_nothing_to_delete_returns_zero(self, user):
        make_session(user)

        assert delete_orphaned_sessions() == (0, {})

    def test_a_session_whose_last_user_left_becomes_an_orphan(self, user):
        session = make_session(user)
        session.users.remove(user)

        delete_orphaned_sessions()

        assert not SwipeSession.objects.filter(pk=session.pk).exists()

    def test_deleting_a_session_also_deletes_its_candidates(self, movie):
        orphan = make_session()
        SwipeSessionCandidate.objects.create(
            session=orphan, movie=movie, score=0.5, position=1
        )

        delete_orphaned_sessions()

        assert not SwipeSessionCandidate.objects.filter(movie=movie).exists()

    def test_only_the_given_sessions_are_considered(self):
        wanted = make_session()
        other_orphan = make_session()

        delete_orphaned_sessions(session_ids=[wanted.pk])

        assert not SwipeSession.objects.filter(pk=wanted.pk).exists()
        assert SwipeSession.objects.filter(pk=other_orphan.pk).exists()

    def test_given_sessions_that_still_have_users_are_kept(self, user):
        active = make_session(user)
        orphan = make_session()

        delete_orphaned_sessions(session_ids=[active.pk, orphan.pk])

        assert SwipeSession.objects.filter(pk=active.pk).exists()
        assert not SwipeSession.objects.filter(pk=orphan.pk).exists()

    def test_an_empty_list_of_ids_deletes_nothing(self):
        orphan = make_session()

        assert delete_orphaned_sessions(session_ids=[]) == (0, {})

        assert SwipeSession.objects.filter(pk=orphan.pk).exists()

    def test_any_iterable_of_ids_is_accepted(self):
        orphan = make_session()

        delete_orphaned_sessions(session_ids=(orphan.pk,))

        assert not SwipeSession.objects.filter(pk=orphan.pk).exists()
