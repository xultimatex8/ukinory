import pytest
from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.common.enums import InviteStatus, InviteType
from apps.common.exceptions import SessionFullError
from apps.invites.models import Invite


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
class TestInviteAcceptView:
    def test_requires_authentication(
        self,
        api_client,
        user,
    ):
        invite = Invite.objects.create(
            inviter=user,
            type=InviteType.COMPARISON,
            status=InviteStatus.PENDING,
            code="test-code",
            expires_at=timezone.now() + timedelta(minutes=5),
        )

        response = api_client.post(
            reverse(
                "invite-accept",
                kwargs={"code": invite.code},
            ),
        )

        assert response.status_code == 401

    def test_returns_404_when_invite_does_not_exist(
        self,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)

        response = api_client.post(
            reverse(
                "invite-accept",
                kwargs={"code": "does-not-exist"},
            ),
        )

        assert response.status_code == 404
        assert response.data == {
            "detail": "Invite not found.",
        }

    def test_cannot_accept_own_invite(
        self,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)

        invite = Invite.objects.create(
            inviter=user,
            type=InviteType.COMPARISON,
            status=InviteStatus.PENDING,
            code="own-invite",
            expires_at=timezone.now() + timedelta(minutes=5),
        )

        response = api_client.post(
            reverse(
                "invite-accept",
                kwargs={"code": invite.code},
            ),
        )

        assert response.status_code == 400
        assert response.data == {
            "detail": "You cannot accept your own invite.",
        }

    def test_returns_409_when_invite_is_already_accepted(
        self,
        api_client,
        user,
        other_user,
    ):
        api_client.force_authenticate(user=other_user)

        invite = Invite.objects.create(
            inviter=user,
            accepted_by=other_user,
            type=InviteType.COMPARISON,
            status=InviteStatus.ACCEPTED,
            code="accepted-invite",
            expires_at=timezone.now() + timedelta(minutes=5),
        )

        response = api_client.post(
            reverse(
                "invite-accept",
                kwargs={"code": invite.code},
            ),
        )

        assert response.status_code == 409
        assert response.data == {
            "detail": "This invite has already been accepted.",
        }

    def test_returns_410_when_invite_is_expired(
        self,
        api_client,
        user,
        other_user,
    ):
        api_client.force_authenticate(user=other_user)

        invite = Invite.objects.create(
            inviter=user,
            type=InviteType.COMPARISON,
            status=InviteStatus.PENDING,
            code="expired-invite",
            expires_at=timezone.now() - timedelta(seconds=1),
        )

        response = api_client.post(
            reverse(
                "invite-accept",
                kwargs={"code": invite.code},
            ),
        )

        assert response.status_code == 410
        assert response.data == {
            "detail": "This invite has expired.",
        }

    def _pending_invite(self, inviter, code="fresh-invite"):
        return Invite.objects.create(
            inviter=inviter,
            type=InviteType.COMPARISON,
            status=InviteStatus.PENDING,
            code=code,
            expires_at=timezone.now() + timedelta(minutes=5),
        )

    def _accept_url(self, invite):
        return reverse("invite-accept", kwargs={"code": invite.code})

    @patch("apps.invites.registry.get_acceptance_handler")
    def test_accepts_invite_and_returns_target(
        self,
        mock_get_handler,
        api_client,
        user,
        other_user,
    ):
        target = MagicMock()
        target.pk = 42
        handler = MagicMock(return_value=target)
        mock_get_handler.return_value = handler
        invite = self._pending_invite(user)
        api_client.force_authenticate(user=other_user)

        response = api_client.post(self._accept_url(invite))

        assert response.status_code == 201
        assert response.data["target"] == {
            "id": 42,
            "type": InviteType.COMPARISON,
        }
        assert "invite" in response.data
        mock_get_handler.assert_called_once_with(InviteType.COMPARISON)
        handler.assert_called_once()
        invite.refresh_from_db()
        assert invite.status == InviteStatus.ACCEPTED
        assert invite.accepted_by == other_user
        assert invite.accepted_at is not None

    @patch("apps.invites.registry.get_acceptance_handler")
    def test_invite_can_only_be_accepted_once(
        self,
        mock_get_handler,
        api_client,
        user,
        other_user,
    ):
        mock_get_handler.return_value = MagicMock(return_value=MagicMock(pk=1))
        invite = self._pending_invite(user)
        api_client.force_authenticate(user=other_user)

        first = api_client.post(self._accept_url(invite))
        second = api_client.post(self._accept_url(invite))

        assert first.status_code == 201
        assert second.status_code == 409
        assert second.data == {
            "detail": "This invite has already been accepted.",
        }

    @patch("apps.invites.registry.get_acceptance_handler")
    def test_invite_stays_pending_when_target_rejects_the_user(
        self,
        mock_get_handler,
        api_client,
        user,
        other_user,
    ):
        mock_get_handler.return_value = MagicMock(side_effect=SessionFullError)
        invite = self._pending_invite(user)
        api_client.force_authenticate(user=other_user)

        response = api_client.post(self._accept_url(invite))

        assert 400 <= response.status_code < 500
        invite.refresh_from_db()
        assert invite.status == InviteStatus.PENDING
        assert invite.accepted_by is None

    def test_rejects_unsupported_methods(self, api_client, user, other_user):
        invite = self._pending_invite(user)
        api_client.force_authenticate(user=other_user)

        response = api_client.get(self._accept_url(invite))

        assert response.status_code == 405
