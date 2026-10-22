from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest
from django.test import override_settings

from apps.common.exceptions import (
    AIUnavailableError,
    NotSessionMemberError,
    SessionFinishedError,
    SessionNotFoundError,
)
from apps.common.services.gemini import DEFAULT_MODEL, Completion
from apps.swipe_sessions.exceptions import (
    CandidateNotFoundError,
    JustificationUnavailableError,
)
from apps.swipe_sessions.models import (
    CandidateJustification,
    SwipeSessionCandidate,
)
from apps.swipe_sessions.services.justification import (
    DEFAULT_MAX_HISTORY_MOVIES,
    DEFAULT_MAX_OUTPUT_TOKENS,
    JOINT_MAX_HISTORY_MOVIES,
    JOINT_MAX_OUTPUT_TOKENS,
    JustificationClient,
    _build_joint_prompt,
    _build_prompt,
    _history_lines,
    _recent_liked_ratings,
    ensure_candidate_justification,
    ensure_joint_justification,
    get_candidate_justification,
)
from datetime import date
from apps.common.enums import SessionStatus, SessionType, SwipeSessionType
from apps.swipe_sessions.models import SwipeSession
from apps.movies.models import Movie
from apps.library.models import Rating


@pytest.fixture
def movie(db):
    return Movie.objects.create(tmdb_id=438631, title="Dune", release_year=2021)

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

@pytest.fixture
def candidate(swipe_session, movie):
    return SwipeSessionCandidate.objects.create(
        session=swipe_session, movie=movie, score=0.9, position=1
    )



class TestJustificationClient:
    @patch("apps.common.services.gemini.genai.Client")
    def test_uses_default_settings(self, mock_client):
        client = JustificationClient()

        assert client.model == DEFAULT_MODEL
        mock_client.assert_called_once_with(
            api_key=client.api_key,
        )

    @patch("apps.common.services.gemini.genai.Client")
    @override_settings(GEMINI_API_KEY="test-api-key")
    def test_uses_custom_settings(self, mock_client):
        client = JustificationClient(
            api_key="test-api-key",
            model="custom-model",
        )

        assert client.model == "custom-model"
        mock_client.assert_called_once_with(api_key="test-api-key")

    @patch.object(JustificationClient, "complete")
    @patch("apps.swipe_sessions.services.justification._build_prompt")
    @patch(
        "apps.swipe_sessions.services.justification._recent_liked_ratings"
    )
    @patch("apps.common.services.gemini.genai.Client")
    def test_generate_uses_primary_model(
        self,
        mock_client,
        mock_history,
        mock_build_prompt,
        mock_complete,
    ):
        history = [MagicMock()]
        mock_history.return_value = history
        mock_build_prompt.return_value = "test prompt"
        mock_complete.return_value = Completion(
            text="  Great recommendation.  ",
        )

        client = JustificationClient(
            api_key="test-key",
            model="primary-model",
        )

        movie = MagicMock()
        movie.pk = 123

        result = client.generate(
            user=MagicMock(),
            movie=movie,
        )

        assert result == "  Great recommendation.  "

        mock_history.assert_called_once()
        mock_build_prompt.assert_called_once_with(
            movie,
            history,
        )
        mock_complete.assert_called_once_with(
            "test prompt",
            max_output_tokens=80,
            label="justification for movie 123",
        )

        mock_client.return_value.models.generate_content.assert_not_called()

    @patch.object(JustificationClient, "complete")
    @patch("apps.swipe_sessions.services.justification._build_prompt")
    @patch(
        "apps.swipe_sessions.services.justification._recent_liked_ratings"
    )
    @patch("apps.common.services.gemini.genai.Client")
    def test_generate_returns_empty_string_when_primary_fail(
        self,
        mock_client,
        mock_history,
        mock_build_prompt,
        mock_complete,
    ):
        mock_history.return_value = []
        mock_build_prompt.return_value = "test prompt"
        mock_complete.side_effect = AIUnavailableError("Primary model failed")

        client = JustificationClient(
            api_key="test-key",
            model="primary-model",
        )

        movie = MagicMock()
        movie.pk = 123

        with pytest.raises(JustificationUnavailableError):
            client.generate(
                user=MagicMock(),
                movie=movie,
            )

        mock_complete.assert_called_once_with(
            "test prompt",
            max_output_tokens=80,
            label="justification for movie 123",
        )

    @patch.object(JustificationClient, "complete")
    @patch("apps.swipe_sessions.services.justification._build_prompt")
    @patch(
        "apps.swipe_sessions.services.justification._recent_liked_ratings"
    )
    @patch("apps.common.services.gemini.genai.Client")
    def test_generate_raises_when_quota_is_exceeded(
        self,
        mock_client,
        mock_history,
        mock_build_prompt,
        mock_complete,
    ):
        mock_history.return_value = []
        mock_build_prompt.return_value = "test prompt"
        mock_complete.side_effect = AIUnavailableError("Quota exceeded")

        client = JustificationClient(
            api_key="test-key",
            model="primary-model",
        )

        movie = MagicMock()
        movie.pk = 123

        with pytest.raises(JustificationUnavailableError):
            client.generate(
                user=MagicMock(),
                movie=movie,
            )

        mock_complete.assert_called_once()
        mock_client.return_value.models.generate_content.assert_not_called()


class TestEnsureCandidateJustification:
    @pytest.mark.django_db
    def test_returns_existing_justification(
        self,
        user,
        swipe_session,
        movie,
    ):
        candidate = SwipeSessionCandidate.objects.create(
            session=swipe_session,
            movie=movie,
            score=0.85,
            position=1,
        )

        justification = CandidateJustification.objects.create(
            candidate=candidate,
            text="You liked similar movies.",
            model_version="test-model",
        )

        with patch(
            "apps.swipe_sessions.services.justification.JustificationClient"
        ) as mock_client:
            result = ensure_candidate_justification(
                candidate=candidate,
                user=user,
            )

        assert result == justification
        mock_client.assert_not_called()

    @pytest.mark.django_db
    def test_generates_and_creates_justification(
        self,
        user,
        swipe_session,
        movie,
    ):
        candidate = SwipeSessionCandidate.objects.create(
            session=swipe_session,
            movie=movie,
            score=0.85,
            position=1,
        )

        mock_client = MagicMock()
        mock_client.model = "test-model"
        mock_client.generate.return_value = "You liked similar movies."

        with patch(
            "apps.swipe_sessions.services.justification.JustificationClient",
            return_value=mock_client,
        ):
            result = ensure_candidate_justification(
                candidate=candidate,
                user=user,
            )

        assert result.text == "You liked similar movies."
        assert result.model_version == "test-model"

        mock_client.generate.assert_called_once_with(
            user=user,
            movie=movie,
        )

        assert CandidateJustification.objects.filter(
            candidate=candidate,
            text="You liked similar movies.",
        ).exists()

    @pytest.mark.django_db
    def test_regenerates_empty_existing_justification(
        self,
        user,
        swipe_session,
        movie,
    ):
        candidate = SwipeSessionCandidate.objects.create(
            session=swipe_session,
            movie=movie,
            score=0.85,
            position=1,
        )

        existing = CandidateJustification.objects.create(
            candidate=candidate,
            text="",
            model_version="old-model",
        )

        mock_client = MagicMock()
        mock_client.model = "new-model"
        mock_client.generate.return_value = "New justification."

        with patch(
            "apps.swipe_sessions.services.justification.JustificationClient",
            return_value=mock_client,
        ):
            result = ensure_candidate_justification(
                candidate=candidate,
                user=user,
            )

        result.refresh_from_db()

        assert result.pk == existing.pk
        assert result.text == "New justification."
        assert result.model_version == "new-model"

        mock_client.generate.assert_called_once_with(
            user=user,
            movie=movie,
        )


class TestGetCandidateJustification:
    @pytest.mark.django_db
    def test_raises_when_session_does_not_exist(self, user):
        with pytest.raises(SessionNotFoundError):
            get_candidate_justification(
                user=user,
                session_id=999999,
                candidate_id=1,
            )

    @pytest.mark.django_db
    def test_raises_when_user_is_not_session_member(
        self,
        user,
        swipe_session,
    ):
        with pytest.raises(NotSessionMemberError):
            get_candidate_justification(
                user=user,
                session_id=swipe_session.pk,
                candidate_id=1,
            )

    @pytest.mark.django_db
    def test_raises_when_candidate_does_not_exist(
        self,
        user,
        swipe_session,
    ):
        swipe_session.users.add(user)

        with pytest.raises(CandidateNotFoundError):
            get_candidate_justification(
                user=user,
                session_id=swipe_session.pk,
                candidate_id=999999,
            )

    @pytest.mark.django_db
    def test_raises_when_candidate_belongs_to_another_session(
        self,
        user,
        swipe_session,
        another_swipe_session,
        movie,
    ):
        swipe_session.users.add(user)

        candidate = SwipeSessionCandidate.objects.create(
            session=another_swipe_session,
            movie=movie,
            score=0.85,
            position=1,
        )

        with pytest.raises(CandidateNotFoundError):
            get_candidate_justification(
                user=user,
                session_id=swipe_session.pk,
                candidate_id=candidate.pk,
            )

    @pytest.mark.django_db
    def test_returns_candidate_and_justification(
        self,
        user,
        swipe_session,
        movie,
    ):
        swipe_session.users.add(user)

        candidate = SwipeSessionCandidate.objects.create(
            session=swipe_session,
            movie=movie,
            score=0.85,
            position=1,
        )

        justification = CandidateJustification.objects.create(
            candidate=candidate,
            text="You may enjoy this movie.",
            model_version="test-model",
        )

        with patch(
            "apps.swipe_sessions.services.justification.ensure_candidate_justification",
            return_value=justification,
        ) as ensure_justification:
            result_candidate, result_justification = (
                get_candidate_justification(
                    user=user,
                    session_id=swipe_session.pk,
                    candidate_id=candidate.pk,
                )
            )

        assert result_candidate == candidate
        assert result_justification == justification

        ensure_justification.assert_called_once_with(
            candidate=candidate,
            user=user,
        )


class TestBuildPrompt:
    def test_includes_movie_information_and_history(self):
        movie = MagicMock()
        movie.title = "Dune"
        movie.release_year = 2021
        movie.wikidata_description = "A science fiction film."

        genre = MagicMock()
        genre.name = "Science Fiction"
        movie.genres.all.return_value = [genre]

        rating = SimpleNamespace(
            title="Interstellar",
            release_year=2014,
            rating=5,
        )

        prompt = _build_prompt(
            movie=movie,
            history=[rating],
        )

        assert "Dune (2021)" in prompt
        assert "A science fiction film." in prompt
        assert "Science Fiction" in prompt
        assert "Interstellar (2014): 5/5" in prompt

    def test_uses_default_text_when_history_is_empty(self):
        movie = MagicMock()
        movie.title = "Dune"
        movie.release_year = 2021
        movie.wikidata_description = "A science fiction film."
        movie.genres.all.return_value = []

        prompt = _build_prompt(
            movie=movie,
            history=[],
        )

        assert "No rating history yet." in prompt


@pytest.mark.django_db
def test_recent_liked_ratings_respects_max_history(
    user,
    movie,
):
    from apps.library.models import Rating

    Rating.objects.create(
        user=user,
        movie=movie,
        rating=5,
    )

    with patch(
        "apps.swipe_sessions.services.justification.DEFAULT_MAX_HISTORY_MOVIES",
        1,
    ):
        result = _recent_liked_ratings(user)

    assert len(result) <= 1


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


MODULE = "apps.swipe_sessions.services.justification"


def movie_mock(pk=7, genres=("Drama",)):
    movie = MagicMock()
    movie.pk = pk
    movie.title = "Dune"
    movie.release_year = 2021
    movie.wikidata_description = "A science fiction film."
    movie.genres.all.return_value = [SimpleNamespace(name=name) for name in genres]
    return movie


class TestGenerateDetails:
    @patch.object(JustificationClient, "complete")
    @patch(f"{MODULE}._build_prompt", return_value="solo prompt")
    @patch(f"{MODULE}._recent_liked_ratings", return_value=[])
    @patch("apps.common.services.gemini.genai.Client")
    def test_the_solo_history_uses_the_default_limit(
        self, mock_client, mock_history, mock_prompt, mock_complete
    ):
        mock_complete.return_value = Completion(text="text")
        user = MagicMock()

        JustificationClient(api_key="test-key").generate(user=user, movie=movie_mock())

        mock_history.assert_called_once_with(user)

    def test_joint_generation_allows_longer_answers_but_shorter_histories(self):
        assert JOINT_MAX_OUTPUT_TOKENS > DEFAULT_MAX_OUTPUT_TOKENS
        assert JOINT_MAX_HISTORY_MOVIES < DEFAULT_MAX_HISTORY_MOVIES


class TestGenerateJoint:
    @patch.object(JustificationClient, "complete")
    @patch(f"{MODULE}._build_joint_prompt", return_value="joint prompt")
    @patch(f"{MODULE}._recent_liked_ratings")
    @patch("apps.common.services.gemini.genai.Client")
    def test_builds_one_history_per_user_and_asks_for_a_longer_answer(
        self, mock_client, mock_history, mock_prompt, mock_complete
    ):
        mock_history.side_effect = [["a"], ["b"]]
        mock_complete.return_value = Completion(text="They both like sci-fi.")
        users = [MagicMock(), MagicMock()]
        movie = movie_mock(pk=7)

        result = JustificationClient(api_key="test-key").generate_joint(
            users=users, movie=movie
        )

        assert result == "They both like sci-fi."
        assert mock_history.call_args_list == [
            call(users[0], JOINT_MAX_HISTORY_MOVIES),
            call(users[1], JOINT_MAX_HISTORY_MOVIES),
        ]
        mock_prompt.assert_called_once_with(movie, [["a"], ["b"]])
        mock_complete.assert_called_once_with(
            "joint prompt",
            max_output_tokens=JOINT_MAX_OUTPUT_TOKENS,
            label="justification for movie 7",
        )

    @patch.object(JustificationClient, "complete")
    @patch(f"{MODULE}._build_joint_prompt", return_value="joint prompt")
    @patch(f"{MODULE}._recent_liked_ratings", return_value=[])
    @patch("apps.common.services.gemini.genai.Client")
    def test_an_unavailable_model_is_reported_as_unavailable_justification(
        self, mock_client, mock_history, mock_prompt, mock_complete
    ):
        mock_complete.side_effect = AIUnavailableError("down")

        with pytest.raises(JustificationUnavailableError) as info:
            JustificationClient(api_key="test-key").generate_joint(
                users=[MagicMock(), MagicMock()], movie=movie_mock()
            )

        assert isinstance(info.value.__cause__, AIUnavailableError)


@pytest.mark.django_db
class TestEnsureJointJustification:
    def fake_client(self, text="They both like thrillers."):
        client = MagicMock()
        client.model = "joint-model"
        client.generate_joint.return_value = text
        return client

    def test_an_existing_justification_is_returned_without_calling_the_model(
        self, user, another_user, candidate
    ):
        existing = CandidateJustification.objects.create(
            candidate=candidate, text="Already there.", model_version="m"
        )

        with patch(f"{MODULE}.JustificationClient") as client_cls:
            result = ensure_joint_justification(candidate, [user, another_user])

        assert result == existing
        client_cls.assert_not_called()

    def test_a_new_justification_is_generated_for_both_users_and_stored(
        self, user, another_user, candidate
    ):
        client = self.fake_client()
        users = [user, another_user]

        with patch(f"{MODULE}.JustificationClient", return_value=client):
            result = ensure_joint_justification(candidate, users)

        client.generate_joint.assert_called_once_with(users=users, movie=candidate.movie)
        assert result.text == "They both like thrillers."
        assert result.model_version == "joint-model"
        assert CandidateJustification.objects.filter(
            candidate=candidate, text="They both like thrillers."
        ).exists()

    def test_an_empty_justification_is_regenerated_in_place(
        self, user, another_user, candidate
    ):
        existing = CandidateJustification.objects.create(
            candidate=candidate, text="", model_version="old"
        )

        with patch(f"{MODULE}.JustificationClient", return_value=self.fake_client("New text.")):
            result = ensure_joint_justification(candidate, [user, another_user])

        assert result.pk == existing.pk
        assert result.text == "New text."
        assert result.model_version == "joint-model"

    def test_a_failure_stores_nothing(self, user, another_user, candidate):
        client = self.fake_client()
        client.generate_joint.side_effect = JustificationUnavailableError

        with patch(f"{MODULE}.JustificationClient", return_value=client):
            with pytest.raises(JustificationUnavailableError):
                ensure_joint_justification(candidate, [user, another_user])

        assert not CandidateJustification.objects.filter(candidate=candidate).exists()


@pytest.mark.django_db
class TestGetCandidateJustificationForPairedSessions:
    def test_a_paired_session_gets_a_joint_justification(
        self, user, another_user, movie
    ):
        session = make_paired_session(user, another_user)
        candidate = add_candidate(session, movie)
        joint = CandidateJustification.objects.create(
            candidate=candidate, text="For both.", model_version="m"
        )

        with patch(f"{MODULE}.ensure_session_active"), patch(
            f"{MODULE}.ensure_joint_justification", return_value=joint
        ) as ensure_joint, patch(
            f"{MODULE}.ensure_candidate_justification"
        ) as ensure_solo:
            result_candidate, result = get_candidate_justification(
                user=user, session_id=session.pk, candidate_id=candidate.pk
            )

        assert result_candidate == candidate
        assert result == joint
        ensure_solo.assert_not_called()
        kwargs = ensure_joint.call_args.kwargs
        assert kwargs["candidate"] == candidate
        assert set(kwargs["users"]) == {user, another_user}

    def test_the_session_must_still_be_active(self, user, swipe_session, candidate):
        swipe_session.users.add(user)

        with patch(
            f"{MODULE}.ensure_session_active", side_effect=SessionFinishedError
        ) as ensure_active, patch(
            f"{MODULE}.ensure_candidate_justification"
        ) as ensure_solo:
            with pytest.raises(SessionFinishedError):
                get_candidate_justification(
                    user=user, session_id=swipe_session.pk, candidate_id=candidate.pk
                )

        ensure_active.assert_called_once_with(swipe_session)
        ensure_solo.assert_not_called()

    def test_membership_is_checked_before_anything_else(
        self, user, another_user, swipe_session, candidate
    ):
        swipe_session.users.add(another_user)

        with patch(f"{MODULE}.ensure_session_active") as ensure_active:
            with pytest.raises(NotSessionMemberError):
                get_candidate_justification(
                    user=user, session_id=swipe_session.pk, candidate_id=candidate.pk
                )

        ensure_active.assert_not_called()


@pytest.mark.django_db
class TestRecentLikedRatingsOrdering:
    def rate(self, user, title, rating, watched=None):
        return Rating.objects.create(
            user=user, title=title, release_year=2000, rating=rating,
            liked=False, watched_date=watched,
        )

    def test_best_rated_first_then_most_recently_watched(self, user):
        self.rate(user, "Older five", 5, date(2024, 1, 1))
        self.rate(user, "Newer five", 5, date(2025, 1, 1))
        self.rate(user, "Three", 3, date(2025, 6, 1))

        titles = [r.title for r in _recent_liked_ratings(user)]

        assert titles == ["Newer five", "Older five", "Three"]

    def test_the_limit_keeps_the_best_ones(self, user):
        self.rate(user, "Low", 2, date(2025, 1, 1))
        self.rate(user, "High", 5, date(2025, 1, 1))
        self.rate(user, "Mid", 4, date(2025, 1, 1))

        titles = [r.title for r in _recent_liked_ratings(user, limit=2)]

        assert titles == ["High", "Mid"]

    def test_entries_without_a_rating_are_ignored(self, user):
        self.rate(user, "Liked only", None, date(2025, 1, 1))
        self.rate(user, "Rated", 4, date(2025, 1, 1))

        assert [r.title for r in _recent_liked_ratings(user)] == ["Rated"]

    def test_other_users_ratings_are_ignored(self, user, another_user):
        self.rate(another_user, "Theirs", 5, date(2025, 1, 1))

        assert _recent_liked_ratings(user) == []


class TestHistoryLines:
    def test_each_rating_is_listed_on_its_own_line(self):
        history = [
            SimpleNamespace(title="Alien", release_year=1979, rating=5),
            SimpleNamespace(title="Heat", release_year=1995, rating=4),
        ]

        assert _history_lines(history) == "- Alien (1979): 5/5\n- Heat (1995): 4/5"

    def test_an_empty_history_has_a_placeholder(self):
        assert _history_lines([]) == "No rating history yet."


class TestPromptDetails:
    def test_the_solo_prompt_lists_every_genre(self):
        prompt = _build_prompt(movie_mock(genres=("Drama", "Sci-Fi")), [])

        assert "Genres: Drama, Sci-Fi" in prompt

    def test_the_joint_prompt_describes_the_movie_and_both_histories(self):
        histories = [
            [SimpleNamespace(title="Alien", release_year=1979, rating=5)],
            [SimpleNamespace(title="Heat", release_year=1995, rating=4)],
        ]

        prompt = _build_joint_prompt(movie_mock(), histories)

        assert "Dune (2021)" in prompt
        assert "A science fiction film." in prompt
        assert "Person A's rating history:\n- Alien (1979): 5/5" in prompt
        assert "Person B's rating history:\n- Heat (1995): 4/5" in prompt

    def test_the_joint_prompt_forbids_labels_and_names(self):
        prompt = _build_joint_prompt(movie_mock(), [[], []])

        assert "one of you" in prompt
        assert "never use the labels A/B or any names" in prompt

    def test_empty_joint_histories_use_the_placeholder_for_both_people(self):
        prompt = _build_joint_prompt(movie_mock(), [[], []])

        assert prompt.count("No rating history yet.") == 2

    def test_only_two_people_are_described(self):
        histories = [[], [], []]

        assert "Person C" not in _build_joint_prompt(movie_mock(), histories)
