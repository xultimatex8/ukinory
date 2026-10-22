from types import SimpleNamespace
from unittest.mock import patch

import pytest

from apps.swipe_sessions.models import SwipeSessionCandidate
from apps.swipe_sessions.services.candidate_pool import (
    _already_planned_movie_ids,
    _min_remaining,
    _store_candidates,
    fill_candidate_pool,
    fill_paired_candidate_pool,
)
from apps.common.enums import SessionStatus, SessionType, SwipeAction, SwipeSessionType
from apps.common.exceptions import PartnerNotJoinedError
from apps.library.models import WatchlistEntry
from apps.movies.models import Movie
from apps.swipe_sessions.constants import PAIRED_POOL_SIZE
from apps.swipe_sessions.exceptions import PairedDataMissingError
from apps.swipe_sessions.models import Swipe, SwipeSession


@pytest.fixture
def movie(db):
    return Movie.objects.create(tmdb_id=438631, title="Dune", release_year=2021)

@pytest.fixture
def another_movie(db):
    return Movie.objects.create(tmdb_id=348, title="Alien", release_year=1979)

@pytest.fixture
def swipe_session(db):
    return SwipeSession.objects.create(
        type="solo", session_type=SessionType.SWIPE_SESSION
    )

@pytest.fixture
def another_swipe_session(db):
    return SwipeSession.objects.create(
        type="solo", session_type=SessionType.SWIPE_SESSION
    )



@pytest.mark.django_db
def test_fill_candidate_pool_creates_candidates(user, swipe_session, movie):
    candidates = [
        SimpleNamespace(movie=movie, final_score=0.85),
    ]

    with patch(
        "apps.swipe_sessions.services.candidate_pool.build_hybrid_pool",
        return_value=candidates,
    ) as build_pool:
        result = fill_candidate_pool(
            session=swipe_session,
            user=user,
        )

    build_pool.assert_called_once_with(user)

    assert len(result) == 1

    candidate = result[0]

    assert candidate.session == swipe_session
    assert candidate.movie == movie
    assert candidate.score == 0.85
    assert candidate.position == 1

    assert SwipeSessionCandidate.objects.filter(
        session=swipe_session,
        movie=movie,
    ).exists()


@pytest.mark.django_db
def test_fill_candidate_pool_ignores_existing_movies(
    user,
    swipe_session,
    movie,
    another_movie,
):
    SwipeSessionCandidate.objects.create(
        session=swipe_session,
        movie=movie,
        score=0.90,
        position=1,
    )

    candidates = [
        SimpleNamespace(movie=movie, final_score=0.95),
        SimpleNamespace(movie=another_movie, final_score=0.80),
    ]

    with patch(
        "apps.swipe_sessions.services.candidate_pool.build_hybrid_pool",
        return_value=candidates,
    ):
        result = fill_candidate_pool(
            session=swipe_session,
            user=user,
        )

    assert len(result) == 1

    candidate = result[0]

    assert candidate.movie == another_movie
    assert candidate.score == 0.80
    assert candidate.position == 2

    assert SwipeSessionCandidate.objects.filter(
        session=swipe_session,
    ).count() == 2


@pytest.mark.django_db
def test_fill_candidate_pool_continues_positions(
    user,
    swipe_session,
    movie,
    another_movie,
):
    SwipeSessionCandidate.objects.create(
        session=swipe_session,
        movie=movie,
        score=0.90,
        position=5,
    )

    candidates = [
        SimpleNamespace(movie=another_movie, final_score=0.80),
    ]

    with patch(
        "apps.swipe_sessions.services.candidate_pool.build_hybrid_pool",
        return_value=candidates,
    ):
        result = fill_candidate_pool(
            session=swipe_session,
            user=user,
        )

    assert len(result) == 1
    assert result[0].position == 6


@pytest.mark.django_db
def test_fill_candidate_pool_creates_sequential_positions(
    user,
    swipe_session,
    movie,
    another_movie,
):
    candidates = [
        SimpleNamespace(movie=movie, final_score=0.90),
        SimpleNamespace(movie=another_movie, final_score=0.75),
    ]

    with patch(
        "apps.swipe_sessions.services.candidate_pool.build_hybrid_pool",
        return_value=candidates,
    ):
        result = fill_candidate_pool(
            session=swipe_session,
            user=user,
        )

    assert [candidate.position for candidate in result] == [1, 2]


@pytest.mark.django_db
def test_fill_candidate_pool_returns_empty_when_no_candidates(
    user,
    swipe_session,
):
    with patch(
        "apps.swipe_sessions.services.candidate_pool.build_hybrid_pool",
        return_value=[],
    ):
        result = fill_candidate_pool(
            session=swipe_session,
            user=user,
        )

    assert result == []
    assert not SwipeSessionCandidate.objects.filter(
        session=swipe_session,
    ).exists()


@pytest.mark.django_db
def test_fill_candidate_pool_returns_empty_when_all_movies_exist(
    user,
    swipe_session,
    movie,
):
    SwipeSessionCandidate.objects.create(
        session=swipe_session,
        movie=movie,
        score=0.90,
        position=1,
    )

    candidates = [
        SimpleNamespace(movie=movie, final_score=0.95),
    ]

    with patch(
        "apps.swipe_sessions.services.candidate_pool.build_hybrid_pool",
        return_value=candidates,
    ):
        result = fill_candidate_pool(
            session=swipe_session,
            user=user,
        )

    assert result == []

    assert SwipeSessionCandidate.objects.filter(
        session=swipe_session,
    ).count() == 1


def make_paired_session(*users, status=SessionStatus.ACTIVE):
    session = SwipeSession.objects.create(
        type=SwipeSessionType.PAIRED,
        session_type=SessionType.SWIPE_SESSION,
        status=status,
    )
    session.users.add(*users)
    return session


def add_candidate(session, movie, position=1, score=0.5):
    return SwipeSessionCandidate.objects.create(
        session=session, movie=movie, score=score, position=position
    )


MODULE = "apps.swipe_sessions.services.candidate_pool"
_film_numbers = iter(range(950000, 960000))


def make_movie(title):
    return Movie.objects.create(
        tmdb_id=next(_film_numbers), title=title, release_year=2000
    )


@pytest.fixture
def joint():
    with patch(f"{MODULE}.user_taste_profiles") as profiles, patch(
        f"{MODULE}.find_joint_candidates"
    ) as find:
        profiles.return_value = ["profile-a", "profile-b"]
        find.return_value = []
        yield SimpleNamespace(profiles=profiles, find=find)


@pytest.mark.django_db
class TestStoreCandidates:
    def test_positions_start_at_one_in_an_empty_session(
        self, swipe_session, movie, another_movie
    ):
        rows = _store_candidates(swipe_session, [(movie, 0.9), (another_movie, 0.8)])

        assert [(r.movie, r.score, r.position) for r in rows] == [
            (movie, 0.9, 1),
            (another_movie, 0.8, 2),
        ]

    def test_positions_continue_after_the_last_existing_one(
        self, swipe_session, movie, another_movie
    ):
        add_candidate(swipe_session, movie, position=7)

        rows = _store_candidates(swipe_session, [(another_movie, 0.8)])

        assert rows[0].position == 8

    def test_an_empty_ranking_stores_nothing(self, swipe_session):
        assert _store_candidates(swipe_session, []) == []
        assert not SwipeSessionCandidate.objects.exists()

    def test_the_rows_belong_to_the_session(self, swipe_session, movie):
        rows = _store_candidates(swipe_session, [(movie, 0.5)])

        assert rows[0].session == swipe_session
        assert SwipeSessionCandidate.objects.filter(session=swipe_session).count() == 1


@pytest.mark.django_db
class TestMinRemaining:
    def test_is_the_candidates_left_for_the_user_who_swiped_the_most(
        self, user, another_user, swipe_session
    ):
        candidates = [add_candidate(swipe_session, make_movie(f"F{i}"), i) for i in (1, 2, 3)]
        Swipe.objects.create(user=user, candidate=candidates[0], action=SwipeAction.SKIP)
        Swipe.objects.create(user=user, candidate=candidates[1], action=SwipeAction.SKIP)
        Swipe.objects.create(user=another_user, candidate=candidates[0], action=SwipeAction.SKIP)

        assert _min_remaining(swipe_session, [user, another_user]) == 1

    def test_without_swipes_it_is_the_total_number_of_candidates(
        self, user, another_user, swipe_session
    ):
        for i in (1, 2, 3):
            add_candidate(swipe_session, make_movie(f"F{i}"), i)

        assert _min_remaining(swipe_session, [user, another_user]) == 3

    def test_swipes_in_other_sessions_do_not_count(
        self, user, another_user, swipe_session, another_swipe_session
    ):
        mine = add_candidate(swipe_session, make_movie("Mine"), 1)
        elsewhere = add_candidate(another_swipe_session, make_movie("Elsewhere"), 1)
        Swipe.objects.create(user=user, candidate=elsewhere, action=SwipeAction.SKIP)

        assert _min_remaining(swipe_session, [user, another_user]) == 1
        assert mine.session == swipe_session


@pytest.mark.django_db
class TestAlreadyPlannedMovieIds:
    def test_combines_watchlist_entries_and_watchlist_swipes_of_the_users(
        self, user, another_user, swipe_session
    ):
        listed, swiped = make_movie("Listed"), make_movie("Swiped")
        WatchlistEntry.objects.create(
            user=user, title=listed.title, release_year=2000, movie=listed
        )
        Swipe.objects.create(
            user=another_user,
            candidate=add_candidate(swipe_session, swiped, 1),
            action=SwipeAction.WATCHLIST,
        )

        assert _already_planned_movie_ids([user, another_user]) == {listed.pk, swiped.pk}

    def test_skipped_films_are_not_planned(self, user, swipe_session):
        skipped = make_movie("Skipped")
        Swipe.objects.create(
            user=user,
            candidate=add_candidate(swipe_session, skipped, 1),
            action=SwipeAction.SKIP,
        )

        assert _already_planned_movie_ids([user]) == set()

    def test_watchlist_entries_without_a_matched_film_are_ignored(self, user):
        WatchlistEntry.objects.create(user=user, title="Unmatched", release_year=1999)

        assert _already_planned_movie_ids([user]) == set()

    def test_other_users_plans_are_ignored(self, user, other_user):
        theirs = make_movie("Theirs")
        WatchlistEntry.objects.create(
            user=other_user, title=theirs.title, release_year=2000, movie=theirs
        )

        assert _already_planned_movie_ids([user]) == set()


@pytest.mark.django_db
class TestFillPairedCandidatePool:
    def test_a_session_without_a_partner_cannot_be_filled(self, user, joint):
        session = make_paired_session(user, status=SessionStatus.WAITING)

        with pytest.raises(PartnerNotJoinedError):
            fill_paired_candidate_pool(session)

        joint.profiles.assert_not_called()

    def test_both_users_need_a_taste_profile(self, user, another_user, joint):
        session = make_paired_session(user, another_user)
        joint.profiles.return_value = ["profile-a", None]

        with pytest.raises(PairedDataMissingError):
            fill_paired_candidate_pool(session)

        joint.find.assert_not_called()
        assert not SwipeSessionCandidate.objects.exists()

    def test_stores_the_joint_candidates_with_their_scores(
        self, user, another_user, movie, another_movie, joint
    ):
        session = make_paired_session(user, another_user)
        joint.find.return_value = [
            SimpleNamespace(movie=movie, score=0.7),
            SimpleNamespace(movie=another_movie, score=0.6),
        ]

        rows = fill_paired_candidate_pool(session)

        assert [(r.movie, r.score, r.position) for r in rows] == [
            (movie, 0.7, 1),
            (another_movie, 0.6, 2),
        ]

    def test_an_empty_joint_pool_stores_nothing(self, user, another_user, joint):
        session = make_paired_session(user, another_user)

        assert fill_paired_candidate_pool(session) == []

    def test_the_search_receives_the_users_profiles_and_the_pool_size(
        self, user, another_user, joint
    ):
        session = make_paired_session(user, another_user)

        fill_paired_candidate_pool(session)

        kwargs = joint.find.call_args.kwargs
        assert set(kwargs["users"]) == {user, another_user}
        assert kwargs["profiles"] == ["profile-a", "profile-b"]
        assert kwargs["limit"] == PAIRED_POOL_SIZE
        assert set(joint.profiles.call_args.args[0]) == {user, another_user}

    def test_films_already_in_the_session_or_planned_are_excluded(
        self, user, another_user, other_user, swipe_session, joint
    ):
        session = make_paired_session(user, another_user)
        in_pool, listed, swiped, skipped, others = (
            make_movie(name) for name in ("Pool", "Listed", "Swiped", "Skipped", "Others")
        )
        add_candidate(session, in_pool, 1)
        WatchlistEntry.objects.create(
            user=another_user, title=listed.title, release_year=2000, movie=listed
        )
        Swipe.objects.create(
            user=user,
            candidate=add_candidate(swipe_session, swiped, 1),
            action=SwipeAction.WATCHLIST,
        )
        Swipe.objects.create(
            user=user,
            candidate=add_candidate(swipe_session, skipped, 2),
            action=SwipeAction.SKIP,
        )
        WatchlistEntry.objects.create(
            user=other_user, title=others.title, release_year=2000, movie=others
        )

        fill_paired_candidate_pool(session)

        assert joint.find.call_args.kwargs["exclude_movie_ids"] == {
            in_pool.pk, listed.pk, swiped.pk,
        }

    def test_without_a_threshold_the_pool_is_always_refilled(
        self, user, another_user, joint
    ):
        session = make_paired_session(user, another_user)
        for i in (1, 2, 3):
            add_candidate(session, make_movie(f"F{i}"), i)

        fill_paired_candidate_pool(session)

        joint.find.assert_called_once()

    def test_enough_candidates_left_means_no_refill(self, user, another_user, joint):
        session = make_paired_session(user, another_user)
        for i in (1, 2, 3):
            add_candidate(session, make_movie(f"F{i}"), i)

        result = fill_paired_candidate_pool(session, refill_threshold=2)

        assert result == []
        joint.profiles.assert_not_called()
        joint.find.assert_not_called()

    def test_refills_when_the_remaining_candidates_reach_the_threshold(
        self, user, another_user, joint
    ):
        session = make_paired_session(user, another_user)
        for i in (1, 2, 3):
            add_candidate(session, make_movie(f"F{i}"), i)

        fill_paired_candidate_pool(session, refill_threshold=3)

        joint.find.assert_called_once()

    def test_the_user_closest_to_the_end_decides_when_to_refill(
        self, user, another_user, swipe_session, joint
    ):
        session = make_paired_session(user, another_user)
        candidates = [add_candidate(session, make_movie(f"F{i}"), i) for i in (1, 2, 3)]
        for candidate in candidates:
            Swipe.objects.create(user=user, candidate=candidate, action=SwipeAction.SKIP)

        fill_paired_candidate_pool(session, refill_threshold=2)

        joint.find.assert_called_once()

    def test_the_partner_is_checked_before_the_threshold(self, user, joint):
        session = make_paired_session(user, status=SessionStatus.WAITING)

        with pytest.raises(PartnerNotJoinedError):
            fill_paired_candidate_pool(session, refill_threshold=0)
