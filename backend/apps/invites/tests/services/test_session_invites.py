from __future__ import annotations

from datetime import timedelta
from unittest import mock

import pytest
from django.utils import timezone

from apps.common.enums import (
    InviteStatus,
    InviteType,
    SessionStatus,
    SessionType,
)
from apps.common.exceptions import (
    SessionClosedError,
    SessionFullError,
    SessionNotFoundError,
)
from apps.common.services.sessions import MAX_PARTICIPANTS
from apps.comparisons.models import ComparisonSession
from apps.invites.exceptions import TooManyPendingInvitesError
from apps.invites.models import Invite
from apps.invites.services.invite import (
    MAX_PENDING_INVITES_PER_USER,
    create_invite,
)
from apps.invites.services.session_invites import (
    join_session_from_invite,
    regenerate_session_invite,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def owner(user):
    return user


@pytest.fixture
def guest(another_user):
    return another_user


@pytest.fixture
def fillers(other_user, django_user_model):
    extra = [
        django_user_model.objects.create_user(
            email=f"filler{i}@example.com", username=f"filler{i}", password="pw"
        )
        for i in range(max(MAX_PARTICIPANTS - 2, 0))
    ]
    return [other_user, *extra][: max(MAX_PARTICIPANTS - 1, 0)]


def _room(users, *, status=SessionStatus.WAITING):
    room = ComparisonSession.objects.create(
        session_type=SessionType.COMPARISON_SESSION,
        status=status,
        last_seen_at=timezone.now() - timedelta(hours=1),
    )
    room.users.add(*users)
    return room


def _invite(owner, room):
    return create_invite(
        user=owner, invite_type=InviteType.COMPARISON, session=room
    )


def _full_room(owner, fillers, *, status=SessionStatus.WAITING):
    return _room([owner, *fillers], status=status)


class TestJoinSessionFromInvite:
    def test_invite_without_session_raises_not_found(self, owner, guest):
        invite = create_invite(user=owner, invite_type=InviteType.COMPARISON)

        with pytest.raises(SessionNotFoundError):
            join_session_from_invite(invite, guest, ComparisonSession)

    def test_adds_user_to_waiting_session_and_returns_it(self, owner, guest):
        room = _room([owner])
        invite = _invite(owner, room)

        result = join_session_from_invite(invite, guest, ComparisonSession)

        assert result.pk == room.pk
        assert room.users.filter(pk=guest.pk).exists()

    def test_refreshes_last_seen_at(self, owner, guest):
        room = _room([owner])
        previous = room.last_seen_at
        invite = _invite(owner, room)

        join_session_from_invite(invite, guest, ComparisonSession)

        room.refresh_from_db()
        assert room.last_seen_at > previous

    def test_finished_session_raises_closed(self, owner, guest):
        room = _room([owner], status=SessionStatus.FINISHED)
        invite = _invite(owner, room)

        with pytest.raises(SessionClosedError):
            join_session_from_invite(invite, guest, ComparisonSession)

        assert not room.users.filter(pk=guest.pk).exists()

    def test_finished_session_is_closed_even_when_full(self, owner, guest, fillers):
        room = _full_room(owner, fillers, status=SessionStatus.FINISHED)
        invite = _invite(owner, room)

        with pytest.raises(SessionClosedError):
            join_session_from_invite(invite, guest, ComparisonSession)

    def test_active_session_raises_full(self, owner, guest):
        room = _room([owner], status=SessionStatus.ACTIVE)
        invite = _invite(owner, room)

        with pytest.raises(SessionFullError):
            join_session_from_invite(invite, guest, ComparisonSession)

        assert not room.users.filter(pk=guest.pk).exists()

    def test_waiting_session_at_capacity_raises_full(self, owner, guest, fillers):
        room = _full_room(owner, fillers)
        invite = _invite(owner, room)

        with pytest.raises(SessionFullError):
            join_session_from_invite(invite, guest, ComparisonSession)

        assert room.users.count() == MAX_PARTICIPANTS

    def test_validate_receives_the_locked_session(self, owner, guest):
        room = _room([owner])
        invite = _invite(owner, room)
        validate = mock.Mock()

        join_session_from_invite(invite, guest, ComparisonSession, validate=validate)

        validate.assert_called_once()
        assert validate.call_args.args[0].pk == room.pk

    def test_validate_error_blocks_the_join(self, owner, guest):
        room = _room([owner])
        invite = _invite(owner, room)
        validate = mock.Mock(side_effect=PermissionError("not allowed"))

        with pytest.raises(PermissionError):
            join_session_from_invite(
                invite, guest, ComparisonSession, validate=validate
            )

        assert not room.users.filter(pk=guest.pk).exists()

    def test_validate_runs_before_status_checks(self, owner, guest):
        room = _room([owner], status=SessionStatus.FINISHED)
        invite = _invite(owner, room)
        validate = mock.Mock(side_effect=PermissionError("not allowed"))

        with pytest.raises(PermissionError):
            join_session_from_invite(
                invite, guest, ComparisonSession, validate=validate
            )

    def test_notify_runs_on_commit_with_the_session(
        self, owner, guest, django_capture_on_commit_callbacks
    ):
        room = _room([owner])
        invite = _invite(owner, room)
        notify = mock.Mock()

        with django_capture_on_commit_callbacks(execute=True) as callbacks:
            join_session_from_invite(
                invite, guest, ComparisonSession, notify=notify
            )

        assert len(callbacks) == 1
        notify.assert_called_once()
        assert notify.call_args.args[0].pk == room.pk

    def test_notify_is_not_called_before_commit(
        self, owner, guest, django_capture_on_commit_callbacks
    ):
        room = _room([owner])
        invite = _invite(owner, room)
        notify = mock.Mock()

        with django_capture_on_commit_callbacks(execute=False):
            join_session_from_invite(
                invite, guest, ComparisonSession, notify=notify
            )

        notify.assert_not_called()

    def test_notify_is_not_scheduled_when_join_fails(
        self, owner, guest, fillers, django_capture_on_commit_callbacks
    ):
        room = _full_room(owner, fillers)
        invite = _invite(owner, room)
        notify = mock.Mock()

        with django_capture_on_commit_callbacks(execute=True) as callbacks:
            with pytest.raises(SessionFullError):
                join_session_from_invite(
                    invite, guest, ComparisonSession, notify=notify
                )

        assert callbacks == []
        notify.assert_not_called()

    def test_no_callback_is_scheduled_without_notify(
        self, owner, guest, django_capture_on_commit_callbacks
    ):
        room = _room([owner])
        invite = _invite(owner, room)

        with django_capture_on_commit_callbacks(execute=True) as callbacks:
            join_session_from_invite(invite, guest, ComparisonSession)

        assert callbacks == []


class TestRegenerateSessionInvite:
    @pytest.mark.parametrize(
        "status", [SessionStatus.ACTIVE, SessionStatus.FINISHED]
    )
    def test_closed_session_raises(self, owner, status):
        room = _room([owner], status=status)

        with pytest.raises(SessionClosedError):
            regenerate_session_invite(
                user=owner, session=room, invite_type=InviteType.COMPARISON
            )

    def test_full_session_raises(self, owner, fillers):
        room = _full_room(owner, fillers)

        with pytest.raises(SessionFullError):
            regenerate_session_invite(
                user=owner, session=room, invite_type=InviteType.COMPARISON
            )

    def test_expires_previous_pending_invites_and_creates_a_new_one(self, owner):
        room = _room([owner])
        old = _invite(owner, room)

        new = regenerate_session_invite(
            user=owner, session=room, invite_type=InviteType.COMPARISON
        )

        old.refresh_from_db()
        assert old.status == InviteStatus.EXPIRED
        assert new.pk != old.pk
        assert new.code != old.code
        assert new.status == InviteStatus.PENDING
        assert new.session_id == room.pk
        assert new.inviter == owner
        assert new.type == InviteType.COMPARISON

    def test_works_when_there_is_no_previous_invite(self, owner):
        room = _room([owner])

        invite = regenerate_session_invite(
            user=owner, session=room, invite_type=InviteType.COMPARISON
        )

        assert invite.status == InviteStatus.PENDING

    def test_leaves_unrelated_invites_untouched(self, owner, guest):
        room = _room([owner])
        other_room = _room([owner])
        in_other_room = _invite(owner, other_room)
        by_other_user = create_invite(
            user=guest, invite_type=InviteType.COMPARISON, session=room
        )
        accepted = _invite(owner, room)
        Invite.objects.filter(pk=accepted.pk).update(status=InviteStatus.ACCEPTED)

        regenerate_session_invite(
            user=owner, session=room, invite_type=InviteType.COMPARISON
        )

        for invite, expected in (
            (in_other_room, InviteStatus.PENDING),
            (by_other_user, InviteStatus.PENDING),
            (accepted, InviteStatus.ACCEPTED),
        ):
            invite.refresh_from_db()
            assert invite.status == expected

    def test_respects_the_pending_invite_cap(self, owner):
        room = _room([owner])
        for _ in range(MAX_PENDING_INVITES_PER_USER):
            create_invite(user=owner, invite_type=InviteType.COMPARISON)

        with pytest.raises(TooManyPendingInvitesError):
            regenerate_session_invite(
                user=owner, session=room, invite_type=InviteType.COMPARISON
            )

    def test_regenerating_repeatedly_keeps_a_single_pending_invite(self, owner):
        room = _room([owner])

        for _ in range(3):
            regenerate_session_invite(
                user=owner, session=room, invite_type=InviteType.COMPARISON
            )

        pending = Invite.objects.filter(
            inviter=owner, session_id=room.pk, status=InviteStatus.PENDING
        )
        assert pending.count() == 1
