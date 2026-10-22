from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from apps.common.enums import InviteType, SessionStatus, SessionType, SwipeSessionType
from apps.common.exceptions import SessionClosedError
from apps.invites.services.invite import create_invite
from apps.swipe_sessions.models import SwipeSession
from apps.swipe_sessions.services.invite_handler import (
    _ensure_paired,
    accept_paired_swipe_invite,
)

MODULE = "apps.swipe_sessions.services.invite_handler"


def make_session(owner, session_type=SwipeSessionType.PAIRED):
    session = SwipeSession.objects.create(
        type=session_type, session_type=SessionType.SWIPE_SESSION
    )
    session.users.add(owner)
    return session


class TestEnsurePaired:
    def test_a_paired_session_is_accepted(self):
        _ensure_paired(SimpleNamespace(type=SwipeSessionType.PAIRED))

    def test_any_other_session_type_is_closed_to_invites(self):
        with pytest.raises(SessionClosedError):
            _ensure_paired(SimpleNamespace(type="solo"))


class TestAcceptPairedSwipeInviteDelegation:
    def test_joins_the_swipe_session_validating_that_it_is_paired(self):
        invite, user = object(), object()
        expected = MagicMock()

        with patch(f"{MODULE}.join_session_from_invite", return_value=expected) as join:
            result = accept_paired_swipe_invite(invite, user)

        assert result is expected
        join.assert_called_once()
        assert join.call_args.args == (invite, user, SwipeSession)
        assert join.call_args.kwargs["validate"] is _ensure_paired
        assert set(join.call_args.kwargs) == {"validate", "notify"}

    def test_the_notification_tells_everyone_that_the_partner_joined(self):
        session = SimpleNamespace(pk=42)

        with patch(f"{MODULE}.join_session_from_invite") as join, patch(
            f"{MODULE}.notify_session"
        ) as notify:
            accept_paired_swipe_invite(object(), object())
            join.call_args.kwargs["notify"](session)

        notify.assert_called_once_with(
            42, event="session.updated", reason="partner_joined"
        )

    def test_errors_from_joining_are_not_swallowed(self):
        error = RuntimeError("join failed")

        with patch(f"{MODULE}.join_session_from_invite", side_effect=error):
            with pytest.raises(RuntimeError) as info:
                accept_paired_swipe_invite(object(), object())

        assert info.value is error


@pytest.mark.django_db
class TestAcceptPairedSwipeInvite:
    def invite_for(self, owner, session):
        return create_invite(
            user=owner, invite_type=InviteType.PAIRED_SWIPE, session=session
        )

    def test_the_guest_joins_a_paired_session(self, user, another_user):
        session = make_session(user)
        invite = self.invite_for(user, session)

        result = accept_paired_swipe_invite(invite, another_user)

        assert result.pk == session.pk
        assert session.users.filter(pk=another_user.pk).exists()

    def test_a_non_paired_session_cannot_be_joined_through_an_invite(
        self, user, another_user
    ):
        session = make_session(user, session_type="solo")
        invite = self.invite_for(user, session)

        with pytest.raises(SessionClosedError):
            accept_paired_swipe_invite(invite, another_user)

        assert not session.users.filter(pk=another_user.pk).exists()

    def test_a_started_session_cannot_be_joined(self, user, another_user):
        session = make_session(user)
        SwipeSession.objects.filter(pk=session.pk).update(status=SessionStatus.ACTIVE)
        invite = self.invite_for(user, session)

        with pytest.raises(Exception):
            accept_paired_swipe_invite(invite, another_user)

        assert not session.users.filter(pk=another_user.pk).exists()

    def test_the_session_is_notified_once_the_join_is_committed(
        self, user, another_user, django_capture_on_commit_callbacks
    ):
        session = make_session(user)
        invite = self.invite_for(user, session)

        with patch(f"{MODULE}.notify_session") as notify:
            with django_capture_on_commit_callbacks(execute=True):
                accept_paired_swipe_invite(invite, another_user)

        notify.assert_called_once_with(
            session.pk, event="session.updated", reason="partner_joined"
        )
