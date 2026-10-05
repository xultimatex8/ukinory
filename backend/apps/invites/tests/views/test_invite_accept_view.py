import pytest
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.common.enums import InviteStatus, InviteType
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
