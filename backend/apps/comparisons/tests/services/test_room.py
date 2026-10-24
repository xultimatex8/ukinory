from __future__ import annotations

import uuid
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.common.enums import (
    GenerationStatus,
    InviteStatus,
    InviteType,
    SessionStatus,
    SessionType,
)
from apps.common.exceptions import (
    NotSessionMemberError,
    PartnerNotJoinedError,
    SessionClosedError,
    SessionFullError,
    SessionNotFoundError,
)
from apps.common.services.sessions import STALE_TIMEOUT, touch_session
from apps.comparisons.exceptions import InsufficientDataError
from apps.comparisons.models import Comparison, ComparisonSession
from apps.comparisons.services.invite_handler import accept_comparison_invite
from apps.comparisons.services.room import (
    RUNNING_TIMEOUT,
    _comparison_of,
    _ensure_comparison,
    _is_running,
    build_room_state,
    close_stale_rooms,
    create_room,
    get_user_room,
    heartbeat_room,
    leave_room,
    regenerate_invite,
    request_generation,
    run_generation,
)
from apps.invites.models import Invite
from apps.invites.services.invite import create_invite
from apps.library.models import Rating
from apps.movies.models import Movie
import pytest

User = get_user_model()


@pytest.mark.django_db
class TestRoomService:
    @pytest.fixture(autouse=True)
    def _users(self, user, another_user, other_user):
        self.user = user
        self.partner = another_user
        self.other = other_user

    def _room(
        self,
        *,
        user=None,
        status=SessionStatus.WAITING,
        last_seen_at=None,
    ):
        room = ComparisonSession.objects.create(
            session_type=SessionType.COMPARISON_SESSION,
            status=status,
            last_seen_at=last_seen_at or timezone.now(),
        )
        room.users.add(user or self.user)
        return room

    def _invite(self, *, user=None, room=None, status=InviteStatus.PENDING):
        user = user or self.user
        room = room or self._room(user=user)

        invite = create_invite(
            user=user,
            invite_type=InviteType.COMPARISON,
            session=room,
        )

        if status != InviteStatus.PENDING:
            invite.status = status
            invite.save(update_fields=["status"])

        return invite

    def test_get_user_room_returns_room_for_member(self):
        room = self._room()

        result = get_user_room(
            room_id=room.pk,
            user=self.user,
        )

        assert result.pk == room.pk

    def test_get_user_room_raises_for_missing_room(self):
        with pytest.raises(SessionNotFoundError):
            get_user_room(
                room_id=uuid.uuid4(),
                user=self.user,
            )

    def test_get_user_room_raises_for_invalid_room_id(self):
        with pytest.raises(SessionNotFoundError):
            get_user_room(
                room_id="not-an-id",
                user=self.user,
            )

    def test_get_user_room_raises_for_non_member(self):
        room = self._room()

        with pytest.raises(NotSessionMemberError):
            get_user_room(
                room_id=room.pk,
                user=self.partner,
            )

    def test_comparison_of_returns_comparison(self):
        room = self._room()
        comparison = Comparison.objects.create(session=room)

        assert _comparison_of(room) == comparison

    def test_comparison_of_returns_none_when_missing(self):
        room = self._room()

        assert _comparison_of(room) is None

    def test_touch_session_updates_last_seen_at(self):
        old_time = timezone.now() - timedelta(minutes=10)
        room = self._room(last_seen_at=old_time)

        touch_session(room.pk)

        room.refresh_from_db()

        assert room.last_seen_at > old_time

    def test_heartbeat_room_touches_fresh_room(self):
        old_time = timezone.now() - timedelta(seconds=30)
        room = self._room(last_seen_at=old_time)

        heartbeat_room(room)

        room.refresh_from_db()

        assert room.last_seen_at > old_time
        assert room.status == SessionStatus.WAITING

    def test_heartbeat_room_deletes_stale_waiting_room_and_raises(self):
        room = self._room(
            last_seen_at=(
                timezone.now() - STALE_TIMEOUT - timedelta(seconds=1)
            ),
        )

        with pytest.raises(SessionClosedError):
            heartbeat_room(room)

        assert not ComparisonSession.objects.filter(pk=room.pk).exists()

    def test_heartbeat_room_finishes_stale_active_room_without_raising(self):
        room = self._room(
            status=SessionStatus.ACTIVE,
            last_seen_at=(
                timezone.now() - STALE_TIMEOUT - timedelta(seconds=1)
            ),
        )

        heartbeat_room(room)

        assert room.status == SessionStatus.FINISHED

        room.refresh_from_db()

        assert room.status == SessionStatus.FINISHED

    def test_build_room_state_for_waiting_room(self):
        room = self._room()

        state = build_room_state(room, self.user)

        assert state["id"] == str(room.pk)
        assert state["status"] == SessionStatus.WAITING
        assert state["participants"] == 1
        assert not state["partner_joined"]
        assert state["comparison_id"] is None
        assert state["generation_status"] is None
        assert not state["you_have_data"]
        assert state["partner_has_data"] is None

    def test_build_room_state_for_two_participants(self):
        room = self._room()
        room.users.add(self.partner)

        state = build_room_state(room, self.user)

        assert state["participants"] == 2
        assert state["partner_joined"]
        assert state["comparison_id"] is None
        assert state["generation_status"] is None
        assert not state["you_have_data"]
        assert not state["partner_has_data"]

    def test_build_room_state_includes_comparison_data(self):
        room = self._room(status=SessionStatus.ACTIVE)
        room.users.add(self.partner)

        comparison = Comparison.objects.create(
            session=room,
            generation_status=GenerationStatus.READY,
        )

        state = build_room_state(room, self.user)

        assert state["comparison_id"] == str(comparison.pk)
        assert state["generation_status"] == GenerationStatus.READY

    def test_build_room_state_detects_rating_data(self):
        room = self._room()
        room.users.add(self.partner)

        movie = Movie.objects.create(
            tmdb_id=1,
            title="Dune",
            release_year=2021,
        )

        Rating.objects.create(
            user=self.user,
            title="Dune",
            release_year=2021,
            movie=movie,
            rating=5,
        )

        state = build_room_state(room, self.user)

        assert state["you_have_data"]
        assert not state["partner_has_data"]

    def test_build_room_state_detects_both_users_with_data(self):
        room = self._room()
        room.users.add(self.partner)

        movie_a = Movie.objects.create(
            tmdb_id=1,
            title="Dune",
            release_year=2021,
        )
        movie_b = Movie.objects.create(
            tmdb_id=2,
            title="Interstellar",
            release_year=2014,
        )

        Rating.objects.create(
            user=self.user,
            title="Dune",
            release_year=2021,
            movie=movie_a,
            rating=5,
        )
        Rating.objects.create(
            user=self.partner,
            title="Interstellar",
            release_year=2014,
            movie=movie_b,
            rating=4,
        )

        state = build_room_state(room, self.user)

        assert state["you_have_data"]
        assert state["partner_has_data"]

    def test_create_room_creates_room_with_user_and_invite(self):
        room, invite = create_room(self.user)

        assert room.session_type == SessionType.COMPARISON_SESSION
        assert room.status == SessionStatus.WAITING
        assert room.users.filter(pk=self.user.pk).exists()

        assert invite.inviter == self.user
        assert invite.type == InviteType.COMPARISON
        assert invite.session_id == room.pk
        assert invite.status == InviteStatus.PENDING

    def test_regenerate_invite_expires_existing_pending_invites(self):
        room = self._room()

        old_invite = self._invite(
            user=self.user,
            room=room,
        )

        new_invite = regenerate_invite(
            user=self.user,
            room=room,
        )

        old_invite.refresh_from_db()

        assert old_invite.status == InviteStatus.EXPIRED
        assert new_invite.status == InviteStatus.PENDING
        assert new_invite.session_id == room.pk

    def test_regenerate_invite_only_expires_pending_invites(self):
        room = self._room()

        pending = self._invite(
            user=self.user,
            room=room,
        )
        expired = self._invite(
            user=self.user,
            room=room,
            status=InviteStatus.EXPIRED,
        )

        regenerate_invite(
            user=self.user,
            room=room,
        )

        pending.refresh_from_db()
        expired.refresh_from_db()

        assert pending.status == InviteStatus.EXPIRED
        assert expired.status == InviteStatus.EXPIRED

    def test_regenerate_invite_rejects_non_waiting_room(self):
        room = self._room(
            status=SessionStatus.ACTIVE,
        )

        with pytest.raises(SessionClosedError):
            regenerate_invite(
                user=self.user,
                room=room,
            )

    def test_regenerate_invite_rejects_full_waiting_room(self):
        room = self._room()
        room.users.add(self.partner)

        with pytest.raises(SessionFullError):
            regenerate_invite(
                user=self.user,
                room=room,
            )

    def test_accept_comparison_invite_rejects_invite_without_session(self):
        invite = self._invite()
        invite.session = None
        invite.save(update_fields=["session"])

        with pytest.raises(SessionNotFoundError):
            accept_comparison_invite(
                invite,
                self.partner,
            )

    def test_accept_comparison_invite_rejects_missing_room(self):
        invite = Invite(
            inviter=self.user,
            session_id=uuid.uuid4(),
            type=InviteType.COMPARISON,
            code="missing-room-code",
            expires_at=timezone.now() + timedelta(minutes=5),
        )

        with pytest.raises(SessionNotFoundError):
            accept_comparison_invite(
                invite,
                self.partner,
            )

    def test_accept_comparison_invite_rejects_finished_room(self):
        room = self._room(
            status=SessionStatus.FINISHED,
        )
        invite = self._invite(room=room)

        with pytest.raises(SessionClosedError):
            accept_comparison_invite(
                invite,
                self.partner,
            )

    def test_accept_comparison_invite_rejects_active_room(self):
        room = self._room(
            status=SessionStatus.ACTIVE,
        )
        invite = self._invite(room=room)

        with pytest.raises(SessionFullError):
            accept_comparison_invite(
                invite,
                self.partner,
            )

    def test_accept_comparison_invite_rejects_full_waiting_room(self):
        room = self._room()
        room.users.add(self.partner)

        invite = self._invite(room=room)

        with pytest.raises(SessionFullError):
            accept_comparison_invite(
                invite,
                self.other,
            )

    @mock.patch(
        "apps.comparisons.services.invite_handler.notify_room"
    )
    def test_accept_comparison_invite_adds_user_without_starting_room(
        self,
        mock_notify, django_capture_on_commit_callbacks,
    ):
        room = self._room()
        invite = self._invite(room=room)

        with django_capture_on_commit_callbacks(execute=True):
            result = accept_comparison_invite(
                invite,
                self.partner,
            )

        room.refresh_from_db()

        assert result.pk == room.pk
        assert room.status == SessionStatus.WAITING
        assert room.users.filter(pk=self.partner.pk).exists()

        mock_notify.assert_called_once_with(
            room.pk,
            reason="partner_joined",
        )

    @mock.patch(
        "apps.comparisons.services.invite_handler.notify_room"
    )
    def test_accept_comparison_invite_does_not_create_comparison(
        self,
        mock_notify, django_capture_on_commit_callbacks,
    ):
        room = self._room()
        invite = self._invite(room=room)

        with django_capture_on_commit_callbacks(execute=True):
            accept_comparison_invite(
                invite,
                self.partner,
            )

        assert not Comparison.objects.filter(session=room).exists()

    def test_request_generation_rejects_room_without_partner(self):
        room = self._room(
            status=SessionStatus.WAITING,
        )

        with pytest.raises(PartnerNotJoinedError):
            request_generation(room=room)

        room.refresh_from_db()

        assert room.status == SessionStatus.WAITING
        assert not Comparison.objects.filter(session=room).exists()

    @mock.patch(
        "apps.comparisons.services.room.run_generation"
    )
    def test_request_generation_starts_room_with_both_participants(
        self,
        mock_run_generation,
    ):
        room = self._room()
        room.users.add(self.partner)

        mock_run_generation.return_value = GenerationStatus.RUNNING

        result = request_generation(room=room)

        room.refresh_from_db()
        comparison = Comparison.objects.get(session=room)

        assert result == GenerationStatus.RUNNING
        assert room.status == SessionStatus.ACTIVE
        mock_run_generation.assert_called_once_with(comparison.pk)

    @mock.patch(
        "apps.comparisons.services.room.run_generation"
    )
    def test_request_generation_is_idempotent(
        self,
        mock_run_generation,
    ):
        room = self._room()
        room.users.add(self.partner)

        mock_run_generation.return_value = GenerationStatus.RUNNING

        request_generation(room=room)
        request_generation(room=room)

        assert Comparison.objects.filter(session=room).count() == 1
        assert mock_run_generation.call_count == 2

    @mock.patch(
        "apps.comparisons.services.room.run_generation"
    )
    def test_request_generation_delegates_to_run_generation(
        self,
        mock_run_generation,
    ):
        room = self._room(
            status=SessionStatus.ACTIVE,
        )
        comparison = Comparison.objects.create(
            session=room,
        )

        mock_run_generation.return_value = GenerationStatus.RUNNING

        result = request_generation(room=room)

        assert result == GenerationStatus.RUNNING
        mock_run_generation.assert_called_once_with(
            comparison.pk,
        )

    def test_is_running_returns_true_for_recent_running_generation(self):
        comparison = Comparison(
            generation_status=GenerationStatus.RUNNING,
            generation_started_at=(
                timezone.now() - timedelta(seconds=30)
            ),
        )

        assert _is_running(comparison)

    def test_is_running_returns_false_when_generation_is_not_running(self):
        comparison = Comparison(
            generation_status=GenerationStatus.READY,
            generation_started_at=timezone.now(),
        )

        assert not _is_running(comparison)

    def test_is_running_returns_false_without_start_time(self):
        comparison = Comparison(
            generation_status=GenerationStatus.RUNNING,
            generation_started_at=None,
        )

        assert not _is_running(comparison)

    def test_is_running_returns_false_after_timeout(self):
        comparison = Comparison(
            generation_status=GenerationStatus.RUNNING,
            generation_started_at=(
                timezone.now() - RUNNING_TIMEOUT - timedelta(seconds=1)
            ),
        )

        assert not _is_running(comparison)

    @mock.patch(
        "apps.comparisons.services.room.notify_room"
    )
    @mock.patch(
        "apps.comparisons.services.comparison.get_comparison_result"
    )
    def test_run_generation_marks_ready_when_comparison_succeeds(
        self,
        mock_get_result,
        mock_notify,
    ):
        room = self._room(
            status=SessionStatus.ACTIVE,
        )
        room.users.add(self.partner)

        comparison = Comparison.objects.create(
            session=room,
        )

        result = run_generation(comparison.pk)

        comparison.refresh_from_db()

        assert result == GenerationStatus.READY
        assert comparison.generation_status == GenerationStatus.READY
        assert comparison.generation_started_at is not None

        mock_get_result.assert_called_once_with(
            user=mock.ANY,
            comparison_id=comparison.pk,
        )

        assert mock_notify.call_count == 2
        mock_notify.assert_any_call(
            room.pk,
            reason="generation_started",
        )
        mock_notify.assert_any_call(
            room.pk,
            reason="generation_finished",
        )

    @mock.patch(
        "apps.comparisons.services.room.notify_room"
    )
    @mock.patch(
        "apps.comparisons.services.comparison.get_comparison_result"
    )
    def test_run_generation_marks_needs_data(
        self,
        mock_get_result,
        mock_notify,
    ):
        room = self._room(
            status=SessionStatus.ACTIVE,
        )
        room.users.add(self.partner)

        comparison = Comparison.objects.create(
            session=room,
        )

        mock_get_result.side_effect = InsufficientDataError()

        result = run_generation(comparison.pk)

        comparison.refresh_from_db()

        assert result == GenerationStatus.NEEDS_DATA
        assert comparison.generation_status == GenerationStatus.NEEDS_DATA

    @mock.patch(
        "apps.comparisons.services.room.notify_room"
    )
    @mock.patch(
        "apps.comparisons.services.comparison.get_comparison_result"
    )
    def test_run_generation_marks_failed_on_unexpected_error(
        self,
        mock_get_result,
        mock_notify,
    ):
        room = self._room(
            status=SessionStatus.ACTIVE,
        )
        room.users.add(self.partner)

        comparison = Comparison.objects.create(
            session=room,
        )

        mock_get_result.side_effect = RuntimeError(
            "Unexpected generation error"
        )

        result = run_generation(comparison.pk)

        comparison.refresh_from_db()

        assert result == GenerationStatus.FAILED
        assert comparison.generation_status == GenerationStatus.FAILED

    def test_run_generation_returns_ready_without_running_again(self):
        room = self._room(
            status=SessionStatus.ACTIVE,
        )
        room.users.add(self.partner)

        comparison = Comparison.objects.create(
            session=room,
            generation_status=GenerationStatus.READY,
        )

        with mock.patch(
            "apps.comparisons.services.room.notify_room"
        ) as mock_notify:
            result = run_generation(comparison.pk)

        assert result == GenerationStatus.READY
        mock_notify.assert_not_called()

    def test_run_generation_returns_running_for_recent_generation(self):
        room = self._room(
            status=SessionStatus.ACTIVE,
        )
        room.users.add(self.partner)

        comparison = Comparison.objects.create(
            session=room,
            generation_status=GenerationStatus.RUNNING,
            generation_started_at=timezone.now(),
        )

        with mock.patch(
            "apps.comparisons.services.room.notify_room"
        ) as mock_notify:
            result = run_generation(comparison.pk)

        assert result == GenerationStatus.RUNNING
        mock_notify.assert_not_called()

    def test_run_generation_raises_for_missing_comparison(self):
        with pytest.raises(Comparison.DoesNotExist):
            run_generation(uuid.uuid4())

    def test_close_stale_rooms_deletes_old_waiting_rooms(self):
        stale = self._room(
            last_seen_at=(
                timezone.now()
                - STALE_TIMEOUT
                - timedelta(seconds=1)
            ),
        )
        fresh = self._room()

        count = close_stale_rooms()

        assert count == 1
        assert not ComparisonSession.objects.filter(pk=stale.pk).exists()
        assert ComparisonSession.objects.filter(pk=fresh.pk).exists()

    def test_close_stale_rooms_deletes_rooms_with_null_last_seen_and_old_creation(
        self,
    ):
        old_created = (
            timezone.now()
            - STALE_TIMEOUT
            - timedelta(seconds=1)
        )

        room = ComparisonSession.objects.create(
            session_type=SessionType.COMPARISON_SESSION,
            status=SessionStatus.WAITING,
            last_seen_at=None,
        )
        room.users.add(self.user)

        ComparisonSession.objects.filter(pk=room.pk).update(
            created_at=old_created,
        )

        count = close_stale_rooms()

        assert count == 1
        assert not ComparisonSession.objects.filter(pk=room.pk).exists()

    def test_close_stale_rooms_finishes_old_active_rooms(self):
        room = self._room(
            status=SessionStatus.ACTIVE,
            last_seen_at=(
                timezone.now()
                - STALE_TIMEOUT
                - timedelta(days=1)
            ),
        )

        count = close_stale_rooms()

        assert count == 1

        room.refresh_from_db()

        assert room.status == SessionStatus.FINISHED

    def test_close_stale_rooms_does_not_close_fresh_active_rooms(self):
        room = self._room(
            status=SessionStatus.ACTIVE,
        )

        count = close_stale_rooms()

        assert count == 0
        assert ComparisonSession.objects.filter(pk=room.pk).exists()


def _make_room(users, *, status=SessionStatus.WAITING):
    room = ComparisonSession.objects.create(
        session_type=SessionType.COMPARISON_SESSION,
        status=status,
        last_seen_at=timezone.now(),
    )
    room.users.add(*users)
    return room


@pytest.mark.django_db
class TestLeaveRoom:
    def test_finished_room_is_left_untouched(
        self,
        user,
        another_user,
        mock_notify,
        django_capture_on_commit_callbacks,
    ):
        room = _make_room([user, another_user], status=SessionStatus.FINISHED)

        with django_capture_on_commit_callbacks(execute=True) as callbacks:
            leave_room(room=room, user=user)

        room.refresh_from_db()
        assert room.status == SessionStatus.FINISHED
        assert room.users.filter(pk=user.pk).exists()
        assert callbacks == []
        mock_notify.assert_not_called()

    def test_finished_room_does_not_check_membership(self, user, other_user, mock_notify):
        room = _make_room([user], status=SessionStatus.FINISHED)

        leave_room(room=room, user=other_user)

        assert ComparisonSession.objects.filter(pk=room.pk).exists()

    def test_non_member_cannot_leave_waiting_room(self, user, other_user, mock_notify):
        room = _make_room([user])

        with pytest.raises(NotSessionMemberError):
            leave_room(room=room, user=other_user)

        assert ComparisonSession.objects.filter(pk=room.pk).exists()
        mock_notify.assert_not_called()

    def test_non_member_cannot_leave_active_room(
        self, user, another_user, other_user, mock_notify
    ):
        room = _make_room([user, another_user], status=SessionStatus.ACTIVE)

        with pytest.raises(NotSessionMemberError):
            leave_room(room=room, user=other_user)

        room.refresh_from_db()
        assert room.status == SessionStatus.ACTIVE
        assert room.users.count() == 2
        mock_notify.assert_not_called()

    def test_last_user_leaving_waiting_room_deletes_it_without_notifying(
        self,
        user,
        mock_notify,
        django_capture_on_commit_callbacks,
    ):
        room = _make_room([user])
        room_id = room.pk

        with django_capture_on_commit_callbacks(execute=True):
            leave_room(room=room, user=user)

        assert not ComparisonSession.objects.filter(pk=room_id).exists()
        mock_notify.assert_not_called()

    def test_waiting_room_with_remaining_user_is_kept(
        self,
        user,
        another_user,
        mock_notify,
        django_capture_on_commit_callbacks,
    ):
        room = _make_room([user, another_user])

        with django_capture_on_commit_callbacks(execute=True):
            leave_room(room=room, user=user)

        room.refresh_from_db()
        assert room.status == SessionStatus.WAITING
        assert list(room.users.values_list("pk", flat=True)) == [another_user.pk]

    def test_partner_is_notified_when_leaving_a_waiting_room(
        self,
        user,
        another_user,
        mock_notify,
        django_capture_on_commit_callbacks,
    ):
        room = _make_room([user, another_user])

        with django_capture_on_commit_callbacks(execute=True):
            leave_room(room=room, user=user)

        mock_notify.assert_called_once_with(room.pk, reason="partner_left")

    def test_notification_is_only_sent_after_the_transaction_commits(
        self,
        user,
        another_user,
        mock_notify,
        django_capture_on_commit_callbacks,
    ):
        room = _make_room([user, another_user], status=SessionStatus.ACTIVE)

        with django_capture_on_commit_callbacks(execute=False) as callbacks:
            leave_room(room=room, user=user)

        assert len(callbacks) == 1
        mock_notify.assert_not_called()

        callbacks[0]()

        mock_notify.assert_called_once_with(room.pk, reason="ended")

    @pytest.mark.parametrize(
        "generation_status",
        [GenerationStatus.PENDING, GenerationStatus.NEEDS_DATA],
    )
    def test_active_room_without_a_usable_comparison_is_finished_and_comparison_deleted(
        self,
        user,
        another_user,
        generation_status,
        mock_notify,
        django_capture_on_commit_callbacks,
    ):
        room = _make_room([user, another_user], status=SessionStatus.ACTIVE)
        comparison = Comparison.objects.create(
            session=room, generation_status=generation_status
        )

        with django_capture_on_commit_callbacks(execute=True):
            leave_room(room=room, user=user)

        room.refresh_from_db()
        assert room.status == SessionStatus.FINISHED
        assert not Comparison.objects.filter(pk=comparison.pk).exists()
        assert room.users.count() == 2
        mock_notify.assert_called_once_with(room.pk, reason="ended")

    @pytest.mark.parametrize(
        "generation_status",
        [
            GenerationStatus.READY,
            GenerationStatus.RUNNING,
            GenerationStatus.FAILED,
        ],
    )
    def test_active_room_with_a_generated_or_busy_comparison_is_finished_and_kept(
        self,
        user,
        another_user,
        generation_status,
        mock_notify,
        django_capture_on_commit_callbacks,
    ):
        room = _make_room([user, another_user], status=SessionStatus.ACTIVE)
        comparison = Comparison.objects.create(
            session=room, generation_status=generation_status
        )

        with django_capture_on_commit_callbacks(execute=True):
            leave_room(room=room, user=user)

        room.refresh_from_db()
        assert room.status == SessionStatus.FINISHED
        assert Comparison.objects.filter(pk=comparison.pk).exists()
        mock_notify.assert_called_once_with(room.pk, reason="ended")

    def test_active_room_without_comparison_is_finished_and_members_are_kept(
        self,
        user,
        another_user,
        mock_notify,
        django_capture_on_commit_callbacks,
    ):
        room = _make_room([user, another_user], status=SessionStatus.ACTIVE)

        with django_capture_on_commit_callbacks(execute=True):
            leave_room(room=room, user=user)

        room.refresh_from_db()
        assert room.status == SessionStatus.FINISHED
        assert room.users.filter(pk=user.pk).exists()
        assert room.users.filter(pk=another_user.pk).exists()
        mock_notify.assert_called_once_with(room.pk, reason="ended")

    def test_partner_can_still_leave_after_the_room_has_finished(
        self,
        user,
        another_user,
        mock_notify,
        django_capture_on_commit_callbacks,
    ):
        room = _make_room([user, another_user], status=SessionStatus.ACTIVE)

        with django_capture_on_commit_callbacks(execute=True):
            leave_room(room=room, user=user)
            leave_room(room=room, user=another_user)

        room.refresh_from_db()
        assert room.status == SessionStatus.FINISHED
        mock_notify.assert_called_once_with(room.pk, reason="ended")


@pytest.mark.django_db
class TestEnsureComparison:
    def test_creates_comparison_when_missing(self, user, another_user):
        room = _make_room([user, another_user])

        _ensure_comparison(room)

        assert Comparison.objects.filter(session=room).count() == 1

    def test_is_idempotent_and_keeps_existing_comparison(self, user, another_user):
        room = _make_room([user, another_user])
        existing = Comparison.objects.create(
            session=room, generation_status=GenerationStatus.READY
        )

        _ensure_comparison(room)
        _ensure_comparison(room)

        comparisons = Comparison.objects.filter(session=room)
        assert comparisons.count() == 1
        assert comparisons.get().pk == existing.pk
        assert comparisons.get().generation_status == GenerationStatus.READY


@pytest.fixture
def mock_get_result():
    with mock.patch(
        "apps.comparisons.services.comparison.get_comparison_result"
    ) as patched:
        yield patched


@pytest.fixture
def mock_notify():
    with mock.patch("apps.comparisons.services.room.notify_room") as patched:
        yield patched


@pytest.mark.django_db
class TestRunGenerationRetry:
    def _comparison(self, user, another_user, **kwargs):
        room = _make_room([user, another_user], status=SessionStatus.ACTIVE)
        return Comparison.objects.create(session=room, **kwargs)

    def test_retries_a_failed_generation(
        self, user, another_user, mock_get_result, mock_notify
    ):
        comparison = self._comparison(
            user, another_user, generation_status=GenerationStatus.FAILED
        )

        result = run_generation(comparison.pk)

        assert result == GenerationStatus.READY
        mock_get_result.assert_called_once()
        comparison.refresh_from_db()
        assert comparison.generation_status == GenerationStatus.READY

    def test_retries_a_running_generation_after_timeout(
        self, user, another_user, mock_get_result, mock_notify
    ):
        started = timezone.now() - RUNNING_TIMEOUT - timedelta(seconds=1)
        comparison = self._comparison(
            user,
            another_user,
            generation_status=GenerationStatus.RUNNING,
            generation_started_at=started,
        )

        result = run_generation(comparison.pk)

        assert result == GenerationStatus.READY
        mock_get_result.assert_called_once()
        comparison.refresh_from_db()
        assert comparison.generation_started_at > started

    def test_does_not_notify_when_generation_is_already_ready(
        self, user, another_user, mock_get_result, mock_notify
    ):
        comparison = self._comparison(
            user, another_user, generation_status=GenerationStatus.READY
        )

        result = run_generation(comparison.pk)

        assert result == GenerationStatus.READY
        mock_get_result.assert_not_called()
        mock_notify.assert_not_called()
