from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.common.enums import InviteStatus, InviteType
from apps.invites import registry
from apps.invites.exceptions import (
    InviteAlreadyAcceptedError, InviteExpiredError,
    OwnInviteError, TooManyPendingInvitesError,
)
from apps.invites.services.invite import (
    MAX_PENDING_INVITES_PER_USER, accept_invite,
    create_invite, expire_stale_invites,
)

User = get_user_model()


class InviteServiceTests(TestCase):
    def setUp(self):
        self.inviter = User.objects.create_user(
            email="a@x.com", username="a", password="pw"
        )
        self.guest = User.objects.create_user(is_guest=True)
        self.handler = mock.Mock(return_value=mock.Mock(pk=1))
        patcher = mock.patch.object(
            registry,
            "get_acceptance_handler",
            return_value=self.handler,
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def _invite(self, **kwargs):
        invite = create_invite(
            user=self.inviter, invite_type=InviteType.COMPARISON
        )
        for key, value in kwargs.items():
            setattr(invite, key, value)
        if kwargs:
            invite.save()
        return invite

    def test_accept_calls_handler_and_marks_accepted(self):
        invite = self._invite()
        result = accept_invite(user=self.guest, code=invite.code)
        self.handler.assert_called_once()
        invite.refresh_from_db()
        self.assertEqual(invite.status, InviteStatus.ACCEPTED)
        self.assertEqual(invite.accepted_by, self.guest)
        self.assertEqual(result.target.pk, 1)

    def test_cannot_accept_own_invite(self):
        invite = self._invite()
        with self.assertRaises(OwnInviteError):
            accept_invite(user=self.inviter, code=invite.code)

    def test_single_use(self):
        invite = self._invite()
        accept_invite(user=self.guest, code=invite.code)
        other = User.objects.create_user(is_guest=True)
        with self.assertRaises(InviteAlreadyAcceptedError):
            accept_invite(user=other, code=invite.code)

    def test_expired_invite_is_rejected_and_handler_not_called(self):
        invite = self._invite(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        with self.assertRaises(InviteExpiredError):
            accept_invite(user=self.guest, code=invite.code)
        self.handler.assert_not_called()

    def test_pending_cap(self):
        for _ in range(MAX_PENDING_INVITES_PER_USER):
            self._invite()
        with self.assertRaises(TooManyPendingInvitesError):
            self._invite()

    def test_expire_stale_invites(self):
        stale = self._invite(
            expires_at=timezone.now() - timedelta(days=1)
        )
        fresh = self._invite()
        self.assertEqual(expire_stale_invites(), 1)
        stale.refresh_from_db()
        fresh.refresh_from_db()
        self.assertEqual(stale.status, InviteStatus.EXPIRED)
        self.assertEqual(fresh.status, InviteStatus.PENDING)
