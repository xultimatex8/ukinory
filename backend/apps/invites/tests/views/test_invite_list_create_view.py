import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.common.enums import InviteStatus, InviteType
from apps.invites.models import Invite


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
class TestInviteListCreateView:
    def test_requires_authentication(self, api_client):
        response = api_client.post(
            reverse("invite-list-create"),
            {
                "type": InviteType.COMPARISON.value,
            },
            format="json",
        )

        assert response.status_code == 401

    def test_creates_comparison_invite(
        self,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)

        response = api_client.post(
            reverse("invite-list-create"),
            {
                "type": InviteType.COMPARISON.value,
            },
            format="json",
        )

        assert response.status_code == 201

        invite = Invite.objects.get(code=response.data["code"])

        assert invite.inviter == user
        assert invite.type == InviteType.COMPARISON
        assert invite.status == InviteStatus.PENDING

        assert response.data["type"] == InviteType.COMPARISON
        assert response.data["status"] == InviteStatus.PENDING
        assert response.data["code"] == invite.code

    def test_creates_paired_swipe_invite(
        self,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)

        response = api_client.post(
            reverse("invite-list-create"),
            {
                "type": InviteType.PAIRED_SWIPE.value,
            },
            format="json",
        )

        assert response.status_code == 201

        invite = Invite.objects.get(code=response.data["code"])

        assert invite.inviter == user
        assert invite.type == InviteType.PAIRED_SWIPE
        assert invite.status == InviteStatus.PENDING

    def test_rejects_invalid_invite_type(
        self,
        api_client,
        user,
    ):
        api_client.force_authenticate(user=user)

        response = api_client.post(
            reverse("invite-list-create"),
            {
                "type": "invalid",
            },
            format="json",
        )

        assert response.status_code == 400
        assert Invite.objects.count() == 0

    def test_returns_too_many_pending_invites(
        self,
        api_client,
        user,
    ):
        from datetime import timedelta

        from django.utils import timezone

        api_client.force_authenticate(user=user)

        for _ in range(20):
            Invite.objects.create(
                inviter=user,
                type=InviteType.COMPARISON,
                status=InviteStatus.PENDING,
                code=f"invite-{_}",
                expires_at=timezone.now() + timedelta(minutes=5),
            )

        response = api_client.post(
            reverse("invite-list-create"),
            {
                "type": InviteType.COMPARISON.value,
            },
            format="json",
        )

        assert response.status_code == 429
        assert response.data == {
            "detail": "You have too many pending invites.",
        }
