from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings

from apps.swipe_sessions.exceptions import (
    CandidateNotFoundError,
    NotSessionMemberError,
    SwipeSessionNotFoundError,
)
from apps.swipe_sessions.models import CandidateJustification, SwipeSessionCandidate
from apps.swipe_sessions.services.justification import (
    DEFAULT_FALLBACK_MODEL,
    DEFAULT_MODEL,
    DEFAULT_RECOMMENDATION_JUSTIFICATION_LANGUAGE,
    JustificationClient,
    _build_prompt,
    _recent_liked_ratings,
    ensure_candidate_justification,
    get_candidate_justification,
)


class TestJustificationClient:
    @patch("apps.swipe_sessions.services.justification.genai.Client")
    def test_uses_default_settings(self, mock_client):
        client = JustificationClient()

        assert client.model == DEFAULT_MODEL
        assert client.fallback_model == DEFAULT_FALLBACK_MODEL
        assert client.language == DEFAULT_RECOMMENDATION_JUSTIFICATION_LANGUAGE
        mock_client.assert_called_once()

    @patch("apps.swipe_sessions.services.justification.genai.Client")
    @override_settings(
        RECOMMENDATION_JUSTIFICATION_MODEL="custom-model",
        RECOMMENDATION_JUSTIFICATION_FALLBACK_MODEL="custom-fallback",
        RECOMMENDATION_JUSTIFICATION_LANGUAGE="es",
        GEMINI_API_KEY="test-api-key",
    )
    def test_uses_custom_settings(self, mock_client):
        client = JustificationClient()

        assert client.model == "custom-model"
        assert client.fallback_model == "custom-fallback"
        assert client.language == "es"
        mock_client.assert_called_once_with(api_key="test-api-key")

    @patch("apps.swipe_sessions.services.justification.genai.Client")
    @patch("apps.swipe_sessions.services.justification._build_prompt")
    @patch("apps.swipe_sessions.services.justification._recent_liked_ratings")
    def test_generate_uses_primary_model(
        self,
        mock_history,
        mock_build_prompt,
        mock_client,
    ):
        history = [MagicMock()]
        mock_history.return_value = history
        mock_build_prompt.return_value = "test prompt"

        response = MagicMock()
        response.text = "  Great recommendation.  "

        mock_client.return_value.models.generate_content.return_value = response

        client = JustificationClient(
            api_key="test-key",
            model="primary-model",
            fallback_model="fallback-model",
            language="en",
        )

        movie = MagicMock()
        movie.pk = 123

        result = client.generate(
            user=MagicMock(),
            movie=movie,
        )

        assert result == "Great recommendation."

        mock_history.assert_called_once()
        mock_build_prompt.assert_called_once_with(
            movie,
            history,
            "en",
        )

        mock_client.return_value.models.generate_content.assert_called_once_with(
            model="primary-model",
            contents="test prompt",
        )

    @patch("apps.swipe_sessions.services.justification.genai.Client")
    @patch("apps.swipe_sessions.services.justification._build_prompt")
    @patch("apps.swipe_sessions.services.justification._recent_liked_ratings")
    def test_generate_uses_fallback_model_when_primary_fails(
        self,
        mock_history,
        mock_build_prompt,
        mock_client,
    ):
        mock_history.return_value = []
        mock_build_prompt.return_value = "test prompt"

        response = MagicMock()
        response.text = "Fallback justification"

        generate_content = mock_client.return_value.models.generate_content
        generate_content.side_effect = [
            Exception("Primary model failed"),
            response,
        ]

        client = JustificationClient(
            api_key="test-key",
            model="primary-model",
            fallback_model="fallback-model",
            language="en",
        )

        movie = MagicMock()
        movie.pk = 123

        result = client.generate(
            user=MagicMock(),
            movie=movie,
        )

        assert result == "Fallback justification"

        assert generate_content.call_count == 2

        assert generate_content.call_args_list[0].kwargs == {
            "model": "primary-model",
            "contents": "test prompt",
        }

        assert generate_content.call_args_list[1].kwargs == {
            "model": "fallback-model",
            "contents": "test prompt",
        }

    @patch("apps.swipe_sessions.services.justification.genai.Client")
    @patch("apps.swipe_sessions.services.justification._build_prompt")
    @patch("apps.swipe_sessions.services.justification._recent_liked_ratings")
    def test_generate_returns_empty_string_when_primary_and_fallback_fail(
        self,
        mock_history,
        mock_build_prompt,
        mock_client,
    ):
        mock_history.return_value = []
        mock_build_prompt.return_value = "test prompt"

        mock_client.return_value.models.generate_content.side_effect = [
            Exception("Primary model failed"),
            Exception("Fallback model failed"),
        ]

        client = JustificationClient(
            api_key="test-key",
            model="primary-model",
            fallback_model="fallback-model",
            language="en",
        )

        movie = MagicMock()
        movie.pk = 123

        result = client.generate(
            user=MagicMock(),
            movie=movie,
        )

        assert result == ""

    @patch("apps.swipe_sessions.services.justification._recent_liked_ratings")
    @patch("apps.swipe_sessions.services.justification.genai.Client")
    def test_does_not_use_fallback_when_it_is_same_as_primary(
        self,
        mock_client,
        mock_recent_ratings,
    ):
        mock_recent_ratings.return_value = []

        mock_client.return_value.models.generate_content.side_effect = Exception(
            "Generation failed"
        )

        client = JustificationClient(
            api_key="test-key",
            model="same-model",
            fallback_model="same-model",
            language="en",
        )

        movie = MagicMock()
        movie.pk = 123
        movie.title = "Test Movie"
        movie.release_year = 2025
        movie.wikidata_description = ""
        movie.genres.all.return_value = []

        result = client.generate(
            user=MagicMock(),
            movie=movie,
        )

        assert result == ""

        assert mock_client.return_value.models.generate_content.call_count == 1


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
            language="en",
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
        mock_client.language = "en"
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
        assert result.language == "en"
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
            language="en",
            model_version="old-model",
        )

        mock_client = MagicMock()
        mock_client.language = "en"
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
        with pytest.raises(SwipeSessionNotFoundError):
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
            language="en",
            model_version="test-model",
        )

        with patch(
            "apps.swipe_sessions.services.justification.ensure_candidate_justification",
            return_value=justification,
        ) as ensure_justification:
            result_candidate, result_justification = get_candidate_justification(
                user=user,
                session_id=swipe_session.pk,
                candidate_id=candidate.pk,
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
            language="en",
        )

        assert "Dune (2021)" in prompt
        assert "A science fiction film." in prompt
        assert "Science Fiction" in prompt
        assert "Interstellar (2014): 5/5" in prompt
        assert "Write the response in en." in prompt

    def test_uses_default_text_when_history_is_empty(self):
        movie = MagicMock()
        movie.title = "Dune"
        movie.release_year = 2021
        movie.wikidata_description = "A science fiction film."

        movie.genres.all.return_value = []

        prompt = _build_prompt(
            movie=movie,
            history=[],
            language="es",
        )

        assert "No rating history yet." in prompt
        assert "Write the response in es." in prompt


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
        "apps.swipe_sessions.services.justification.settings.RECOMMENDATION_MAX_HISTORY_MOVIES",
        1,
    ):
        result = _recent_liked_ratings(user)

    assert len(result) <= 1
