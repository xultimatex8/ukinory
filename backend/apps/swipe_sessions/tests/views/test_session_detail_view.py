import uuid

import pytest

from apps.swipe_sessions.views import SwipeSessionDetailView


@pytest.mark.django_db
class TestSwipeSessionDetailView:
    def test_returns_session_for_member(
        self,
        authenticated_get,
        swipe_session,
        user,
    ):
        swipe_session.users.add(user)

        request = authenticated_get()

        response = SwipeSessionDetailView.as_view()(
            request,
            pk=swipe_session.id,
        )

        assert response.status_code == 200

    def test_returns_404_for_nonexistent_session(
        self,
        authenticated_get,
    ):
        request = authenticated_get()

        response = SwipeSessionDetailView.as_view()(
            request,
            pk=uuid.uuid4(),
        )

        assert response.status_code == 404
        assert response.data == {
            "detail": "Swipe session not found."
        }

    def test_returns_403_for_non_member(
        self,
        api_factory,
        another_user,
        swipe_session,
    ):
        request = api_factory.get("/")
        from rest_framework.test import force_authenticate

        force_authenticate(request, user=another_user)

        response = SwipeSessionDetailView.as_view()(
            request,
            pk=swipe_session.id,
        )

        assert response.status_code == 403
        assert response.data == {
            "detail": "You are not a member of this session."
        }

    def test_requires_authentication(
        self,
        api_factory,
        swipe_session,
    ):
        request = api_factory.get("/")

        response = SwipeSessionDetailView.as_view()(
            request,
            pk=swipe_session.id,
        )

        assert response.status_code == 401
