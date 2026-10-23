import uuid
from unittest.mock import MagicMock, patch

import pytest
from django.urls import reverse
from rest_framework.test import APIClient


SESSION_ID = "00000000-0000-0000-0000-000000000001"
SESSION_UUID = uuid.UUID(SESSION_ID)


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
class TestSwipeSessionMatchesView:
    @pytest.fixture(autouse=True)
    def setup_url(self):
        self.url = reverse(
            "swipe-session-matches",
            kwargs={"pk": SESSION_ID},
        )

    def test_requires_authentication(self, api_client):
        response = api_client.get(self.url)

        assert response.status_code == 401

    @patch("apps.swipe_sessions.views.fetch_card_metadata_bulk")
    @patch("apps.swipe_sessions.views.matched_candidates")
    @patch("apps.swipe_sessions.views.require_paired")
    @patch("apps.swipe_sessions.views.get_user_swipe_session")
    def test_returns_matched_candidates_with_metadata(
        self,
        mock_get_session,
        mock_require_paired,
        mock_matched_candidates,
        mock_fetch_metadata,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)

        session = MagicMock()
        mock_get_session.return_value = session

        candidate = MagicMock()
        candidate.pk = "candidate-id"
        candidate.matched_at = "2026-01-10T12:00:00Z"
        candidate.movie.tmdb_id = 550
        candidate.movie.title = "Original title"
        candidate.movie.release_year = 1999

        mock_matched_candidates.return_value = [candidate]
        mock_fetch_metadata.return_value = {
            550: {
                "title": "Fight Club",
                "release_year": 1999,
                "poster_url": "https://example.com/poster.jpg",
            }
        }

        response = api_client.get(self.url)

        assert response.status_code == 200
        assert response.data == [
            {
                "candidate_id": "candidate-id",
                "matched_at": candidate.matched_at,
                "movie": {
                    "tmdb_id": 550,
                    "title": "Fight Club",
                    "release_year": 1999,
                    "poster_url": "https://example.com/poster.jpg",
                },
            }
        ]

        mock_get_session.assert_called_once_with(
            session_id=SESSION_UUID,
            user=user,
        )
        mock_require_paired.assert_called_once_with(session)
        mock_matched_candidates.assert_called_once_with(session)
        mock_fetch_metadata.assert_called_once_with({550})

    @patch("apps.swipe_sessions.views.fetch_card_metadata_bulk")
    @patch("apps.swipe_sessions.views.matched_candidates")
    @patch("apps.swipe_sessions.views.require_paired")
    @patch("apps.swipe_sessions.views.get_user_swipe_session")
    def test_returns_empty_list_when_there_are_no_matches(
        self,
        mock_get_session,
        mock_require_paired,
        mock_matched_candidates,
        mock_fetch_metadata,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)

        session = MagicMock()
        mock_get_session.return_value = session
        mock_matched_candidates.return_value = []

        response = api_client.get(self.url)

        assert response.status_code == 200
        assert response.data == []

        mock_get_session.assert_called_once_with(
            session_id=SESSION_UUID,
            user=user,
        )
        mock_require_paired.assert_called_once_with(session)
        mock_matched_candidates.assert_called_once_with(session)
        mock_fetch_metadata.assert_not_called()

    @patch("apps.swipe_sessions.views.fetch_card_metadata_bulk")
    @patch("apps.swipe_sessions.views.matched_candidates")
    @patch("apps.swipe_sessions.views.require_paired")
    @patch("apps.swipe_sessions.views.get_user_swipe_session")
    def test_falls_back_to_movie_data_when_metadata_is_missing(
        self,
        mock_get_session,
        mock_require_paired,
        mock_matched_candidates,
        mock_fetch_metadata,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)

        session = MagicMock()
        mock_get_session.return_value = session

        candidate = MagicMock()
        candidate.pk = "candidate-id"
        candidate.matched_at = "2026-01-10T12:00:00Z"
        candidate.movie.tmdb_id = 550
        candidate.movie.title = "Original title"
        candidate.movie.release_year = 1999

        mock_matched_candidates.return_value = [candidate]
        mock_fetch_metadata.return_value = {}

        response = api_client.get(self.url)

        assert response.status_code == 200
        assert response.data == [
            {
                "candidate_id": "candidate-id",
                "matched_at": candidate.matched_at,
                "movie": {
                    "tmdb_id": 550,
                    "title": "Original title",
                    "release_year": 1999,
                    "poster_url": "",
                },
            }
        ]

        mock_get_session.assert_called_once_with(
            session_id=SESSION_UUID,
            user=user,
        )
        mock_require_paired.assert_called_once_with(session)
        mock_matched_candidates.assert_called_once_with(session)
        mock_fetch_metadata.assert_called_once_with({550})

    def test_rejects_unsupported_methods(self, api_client, user):
        api_client.force_authenticate(user=user)

        response = api_client.post(self.url)

        assert response.status_code == 405
