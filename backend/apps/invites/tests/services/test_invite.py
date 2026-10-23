import re
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.common.enums import InviteStatus, InviteType, SessionType
from apps.comparisons.models import ComparisonSession
from apps.invites import registry
from apps.invites.exceptions import (
    InviteAlreadyAcceptedError, InviteExpiredError, InviteNotFoundError,
    OwnInviteError, TooManyPendingInvitesError,
)
from apps.invites.models import Invite
from apps.invites.services.invite import (
    INVITE_TTL, MAX_PENDING_INVITES_PER_USER, accept_invite,
    create_invite, expire_stale_invites,
)
import pytest

User = get_user_model()


@pytest.mark.django_db
class TestInviteService:
    @pytest.fixture(autouse=True)
    def _setup(self, user):
        self.inviter = user
        self.guest = User.objects.create_user(is_guest=True)
        self.handler = mock.Mock(return_value=mock.Mock(pk=1))
        with mock.patch.object(
            registry,
            "get_acceptance_handler",
            return_value=self.handler,
        ):
            yield

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
        assert invite.status == InviteStatus.ACCEPTED
        assert invite.accepted_by == self.guest
        assert result.target.pk == 1

    def test_cannot_accept_own_invite(self):
        invite = self._invite()
        with pytest.raises(OwnInviteError):
            accept_invite(user=self.inviter, code=invite.code)

    def test_single_use(self):
        invite = self._invite()
        accept_invite(user=self.guest, code=invite.code)
        other = User.objects.create_user(is_guest=True)
        with pytest.raises(InviteAlreadyAcceptedError):
            accept_invite(user=other, code=invite.code)

    def test_expired_invite_is_rejected_and_handler_not_called(self):
        invite = self._invite(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        with pytest.raises(InviteExpiredError):
            accept_invite(user=self.guest, code=invite.code)
        self.handler.assert_not_called()

    def test_pending_cap(self):
        for _ in range(MAX_PENDING_INVITES_PER_USER):
            self._invite()
        with pytest.raises(TooManyPendingInvitesError):
            self._invite()

    def test_expire_stale_invites(self):
        stale = self._invite(
            expires_at=timezone.now() - timedelta(days=1)
        )
        fresh = self._invite()
        assert expire_stale_invites() == 1
        stale.refresh_from_db()
        fresh.refresh_from_db()
        assert stale.status == InviteStatus.EXPIRED
        assert fresh.status == InviteStatus.PENDING

    def test_create_invite_sets_expected_fields(self):
        before = timezone.now()

        invite = create_invite(
            user=self.inviter, invite_type=InviteType.COMPARISON
        )

        after = timezone.now()
        assert invite.inviter == self.inviter
        assert invite.type == InviteType.COMPARISON
        assert invite.status == InviteStatus.PENDING
        assert invite.session_id is None
        assert invite.expires_at >= before + INVITE_TTL
        assert invite.expires_at <= after + INVITE_TTL

    def test_create_invite_links_session(self):
        room = ComparisonSession.objects.create(
            session_type=SessionType.COMPARISON_SESSION
        )

        invite = create_invite(
            user=self.inviter, invite_type=InviteType.COMPARISON, session=room
        )

        invite.refresh_from_db()
        assert invite.session_id == room.pk

    def test_create_invite_generates_unique_url_safe_codes(self):
        first = self._invite()
        second = self._invite()

        assert first.code != second.code
        for code in (first.code, second.code):
            assert re.search(r"^[A-Za-z0-9_-]{43}$", code)

    def test_accepted_invites_do_not_count_towards_pending_cap(self):
        for _ in range(MAX_PENDING_INVITES_PER_USER):
            self._invite()
        Invite.objects.filter(inviter=self.inviter).update(
            status=InviteStatus.ACCEPTED
        )

        invite = self._invite()

        assert invite.status == InviteStatus.PENDING

    def test_expired_invites_do_not_count_towards_pending_cap(self):
        for _ in range(MAX_PENDING_INVITES_PER_USER):
            self._invite()
        Invite.objects.filter(inviter=self.inviter).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )

        invite = self._invite()

        assert invite.status == InviteStatus.PENDING

    def test_pending_cap_is_per_user(self):
        for _ in range(MAX_PENDING_INVITES_PER_USER):
            create_invite(user=self.guest, invite_type=InviteType.COMPARISON)

        invite = self._invite()

        assert invite.inviter == self.inviter

    def test_accept_unknown_code_raises_not_found(self):
        with pytest.raises(InviteNotFoundError):
            accept_invite(user=self.guest, code="does-not-exist")
        self.handler.assert_not_called()

    def test_accept_passes_invite_and_user_to_handler_for_invite_type(self):
        invite = self._invite()

        with mock.patch.object(
            registry, "get_acceptance_handler", return_value=self.handler
        ) as get_handler:
            accept_invite(user=self.guest, code=invite.code)

        get_handler.assert_called_once_with(InviteType.COMPARISON)
        handler_invite, handler_user = self.handler.call_args.args
        assert handler_invite.pk == invite.pk
        assert handler_user == self.guest

    def test_accept_returns_invite_and_handler_target(self):
        invite = self._invite()

        result = accept_invite(user=self.guest, code=invite.code)

        assert result.invite.pk == invite.pk
        assert result.invite.status == InviteStatus.ACCEPTED
        assert result.target is self.handler.return_value

    def test_accept_records_acceptance_time(self):
        invite = self._invite()
        before = timezone.now()

        accept_invite(user=self.guest, code=invite.code)

        invite.refresh_from_db()
        assert invite.accepted_at >= before
        assert invite.accepted_at <= timezone.now()

    def test_own_invite_check_comes_before_accepted_check(self):
        invite = self._invite(status=InviteStatus.ACCEPTED)

        with pytest.raises(OwnInviteError):
            accept_invite(user=self.inviter, code=invite.code)

    def test_accepted_check_comes_before_expired_check(self):
        invite = self._invite(
            status=InviteStatus.ACCEPTED,
            expires_at=timezone.now() - timedelta(minutes=1),
        )

        with pytest.raises(InviteAlreadyAcceptedError):
            accept_invite(user=self.guest, code=invite.code)
        self.handler.assert_not_called()

    def test_handler_failure_leaves_invite_pending(self):
        invite = self._invite()
        self.handler.side_effect = RuntimeError("handler failed")

        with pytest.raises(RuntimeError):
            accept_invite(user=self.guest, code=invite.code)

        invite.refresh_from_db()
        assert invite.status == InviteStatus.PENDING
        assert invite.accepted_by is None
        assert invite.accepted_at is None

    def test_expire_stale_invites_only_touches_pending_ones(self):
        past = timezone.now() - timedelta(days=1)
        accepted = self._invite(status=InviteStatus.ACCEPTED, expires_at=past)
        already_expired = self._invite(
            status=InviteStatus.EXPIRED, expires_at=past
        )

        assert expire_stale_invites() == 0

        accepted.refresh_from_db()
        already_expired.refresh_from_db()
        assert accepted.status == InviteStatus.ACCEPTED
        assert already_expired.status == InviteStatus.EXPIRED

    def test_expire_stale_invites_returns_zero_without_invites(self):
        assert expire_stale_invites() == 0

    def test_expire_stale_invites_expires_all_stale_ones(self):
        past = timezone.now() - timedelta(hours=1)
        stale = [self._invite(expires_at=past) for _ in range(3)]

        assert expire_stale_invites() == 3

        for invite in stale:
            invite.refresh_from_db()
            assert invite.status == InviteStatus.EXPIRED
