from __future__ import annotations

import uuid
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
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
    _is_running,
    build_room_state,
    close_stale_rooms,
    create_room,
    get_user_room,
    heartbeat_room,
    regenerate_invite,
    request_generation,
    run_generation,
)
from apps.invites.models import Invite
from apps.invites.services.invite import create_invite
from apps.library.models import Rating
from apps.movies.models import Movie

User = get_user_model()


class RoomServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="a@x.com",
            username="a",
            password="pw",
        )
        self.partner = User.objects.create_user(
            email="b@x.com",
            username="b",
            password="pw",
        )
        self.other = User.objects.create_user(
            email="c@x.com",
            username="c",
            password="pw",
        )

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

    # ------------------------------------------------------------------ access

    def test_get_user_room_returns_room_for_member(self):
        room = self._room()

        result = get_user_room(
            room_id=room.pk,
            user=self.user,
        )

        self.assertEqual(result.pk, room.pk)

    def test_get_user_room_raises_for_missing_room(self):
        with self.assertRaises(SessionNotFoundError):
            get_user_room(
                room_id=uuid.uuid4(),
                user=self.user,
            )

    def test_get_user_room_raises_for_invalid_room_id(self):
        with self.assertRaises(SessionNotFoundError):
            get_user_room(
                room_id="not-an-id",
                user=self.user,
            )

    def test_get_user_room_raises_for_non_member(self):
        room = self._room()

        with self.assertRaises(NotSessionMemberError):
            get_user_room(
                room_id=room.pk,
                user=self.partner,
            )

    def test_comparison_of_returns_comparison(self):
        room = self._room()
        comparison = Comparison.objects.create(session=room)

        self.assertEqual(_comparison_of(room), comparison)

    def test_comparison_of_returns_none_when_missing(self):
        room = self._room()

        self.assertIsNone(_comparison_of(room))

    # --------------------------------------------------------------- heartbeat

    def test_touch_session_updates_last_seen_at(self):
        old_time = timezone.now() - timedelta(minutes=10)
        room = self._room(last_seen_at=old_time)

        touch_session(room.pk)

        room.refresh_from_db()

        self.assertGreater(room.last_seen_at, old_time)

    def test_heartbeat_room_touches_fresh_room(self):
        old_time = timezone.now() - timedelta(seconds=30)
        room = self._room(last_seen_at=old_time)

        heartbeat_room(room)

        room.refresh_from_db()

        self.assertGreater(room.last_seen_at, old_time)
        self.assertEqual(room.status, SessionStatus.WAITING)

    def test_heartbeat_room_deletes_stale_waiting_room_and_raises(self):
        room = self._room(
            last_seen_at=(
                timezone.now() - STALE_TIMEOUT - timedelta(seconds=1)
            ),
        )

        with self.assertRaises(SessionClosedError):
            heartbeat_room(room)

        self.assertFalse(
            ComparisonSession.objects.filter(pk=room.pk).exists()
        )

    def test_heartbeat_room_finishes_stale_active_room_without_raising(self):
        room = self._room(
            status=SessionStatus.ACTIVE,
            last_seen_at=(
                timezone.now() - STALE_TIMEOUT - timedelta(seconds=1)
            ),
        )

        heartbeat_room(room)

        self.assertEqual(room.status, SessionStatus.FINISHED)

        room.refresh_from_db()

        self.assertEqual(room.status, SessionStatus.FINISHED)

    # -------------------------------------------------------------------- state

    def test_build_room_state_for_waiting_room(self):
        room = self._room()

        state = build_room_state(room, self.user)

        self.assertEqual(state["id"], str(room.pk))
        self.assertEqual(state["status"], SessionStatus.WAITING)
        self.assertEqual(state["participants"], 1)
        self.assertFalse(state["partner_joined"])
        self.assertIsNone(state["comparison_id"])
        self.assertIsNone(state["generation_status"])
        self.assertFalse(state["you_have_data"])
        self.assertIsNone(state["partner_has_data"])

    def test_build_room_state_for_two_participants(self):
        room = self._room()
        room.users.add(self.partner)

        state = build_room_state(room, self.user)

        self.assertEqual(state["participants"], 2)
        self.assertTrue(state["partner_joined"])
        self.assertIsNone(state["comparison_id"])
        self.assertIsNone(state["generation_status"])
        self.assertFalse(state["you_have_data"])
        self.assertFalse(state["partner_has_data"])

    def test_build_room_state_includes_comparison_data(self):
        room = self._room(status=SessionStatus.ACTIVE)
        room.users.add(self.partner)

        comparison = Comparison.objects.create(
            session=room,
            generation_status=GenerationStatus.READY,
        )

        state = build_room_state(room, self.user)

        self.assertEqual(
            state["comparison_id"],
            str(comparison.pk),
        )
        self.assertEqual(
            state["generation_status"],
            GenerationStatus.READY,
        )

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

        self.assertTrue(state["you_have_data"])
        self.assertFalse(state["partner_has_data"])

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

        self.assertTrue(state["you_have_data"])
        self.assertTrue(state["partner_has_data"])

    # ----------------------------------------------------------- create/invites

    def test_create_room_creates_room_with_user_and_invite(self):
        room, invite = create_room(self.user)

        self.assertEqual(room.session_type, SessionType.COMPARISON_SESSION)
        self.assertEqual(room.status, SessionStatus.WAITING)
        self.assertTrue(
            room.users.filter(pk=self.user.pk).exists()
        )

        self.assertEqual(invite.inviter, self.user)
        self.assertEqual(invite.type, InviteType.COMPARISON)
        self.assertEqual(invite.session_id, room.pk)
        self.assertEqual(invite.status, InviteStatus.PENDING)

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

        self.assertEqual(
            old_invite.status,
            InviteStatus.EXPIRED,
        )
        self.assertEqual(
            new_invite.status,
            InviteStatus.PENDING,
        )
        self.assertEqual(
            new_invite.session_id,
            room.pk,
        )

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

        self.assertEqual(
            pending.status,
            InviteStatus.EXPIRED,
        )
        self.assertEqual(
            expired.status,
            InviteStatus.EXPIRED,
        )

    def test_regenerate_invite_rejects_non_waiting_room(self):
        room = self._room(
            status=SessionStatus.ACTIVE,
        )

        with self.assertRaises(SessionClosedError):
            regenerate_invite(
                user=self.user,
                room=room,
            )

    def test_regenerate_invite_rejects_full_waiting_room(self):
        room = self._room()
        room.users.add(self.partner)

        with self.assertRaises(SessionFullError):
            regenerate_invite(
                user=self.user,
                room=room,
            )

    # --------------------------------------------------------------------- join

    def test_accept_comparison_invite_rejects_invite_without_session(self):
        invite = self._invite()
        invite.session = None
        invite.save(update_fields=["session"])

        with self.assertRaises(SessionNotFoundError):
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

        with self.assertRaises(SessionNotFoundError):
            accept_comparison_invite(
                invite,
                self.partner,
            )

    def test_accept_comparison_invite_rejects_finished_room(self):
        room = self._room(
            status=SessionStatus.FINISHED,
        )
        invite = self._invite(room=room)

        with self.assertRaises(SessionClosedError):
            accept_comparison_invite(
                invite,
                self.partner,
            )

    def test_accept_comparison_invite_rejects_active_room(self):
        room = self._room(
            status=SessionStatus.ACTIVE,
        )
        invite = self._invite(room=room)

        with self.assertRaises(SessionFullError):
            accept_comparison_invite(
                invite,
                self.partner,
            )

    def test_accept_comparison_invite_rejects_full_waiting_room(self):
        room = self._room()
        room.users.add(self.partner)

        invite = self._invite(room=room)

        with self.assertRaises(SessionFullError):
            accept_comparison_invite(
                invite,
                self.other,
            )

    @mock.patch(
        "apps.comparisons.services.invite_handler.notify_room"
    )
    def test_accept_comparison_invite_adds_user_without_starting_room(
        self,
        mock_notify,
    ):
        room = self._room()
        invite = self._invite(room=room)

        with self.captureOnCommitCallbacks(execute=True):
            result = accept_comparison_invite(
                invite,
                self.partner,
            )

        room.refresh_from_db()

        self.assertEqual(result.pk, room.pk)
        self.assertEqual(
            room.status,
            SessionStatus.WAITING,
        )
        self.assertTrue(
            room.users.filter(pk=self.partner.pk).exists()
        )

        mock_notify.assert_called_once_with(
            room.pk,
            reason="partner_joined",
        )

    @mock.patch(
        "apps.comparisons.services.invite_handler.notify_room"
    )
    def test_accept_comparison_invite_does_not_create_comparison(
        self,
        mock_notify,
    ):
        room = self._room()
        invite = self._invite(room=room)

        with self.captureOnCommitCallbacks(execute=True):
            accept_comparison_invite(
                invite,
                self.partner,
            )

        self.assertFalse(
            Comparison.objects.filter(session=room).exists()
        )

    # -------------------------------------------------------- request_generation

    def test_request_generation_rejects_room_without_partner(self):
        room = self._room(
            status=SessionStatus.WAITING,
        )

        with self.assertRaises(PartnerNotJoinedError):
            request_generation(room=room)

        room.refresh_from_db()

        self.assertEqual(room.status, SessionStatus.WAITING)
        self.assertFalse(
            Comparison.objects.filter(session=room).exists()
        )

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

        self.assertEqual(result, GenerationStatus.RUNNING)
        self.assertEqual(room.status, SessionStatus.ACTIVE)
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

        self.assertEqual(
            Comparison.objects.filter(session=room).count(),
            1,
        )
        self.assertEqual(mock_run_generation.call_count, 2)

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

        self.assertEqual(
            result,
            GenerationStatus.RUNNING,
        )
        mock_run_generation.assert_called_once_with(
            comparison.pk,
        )

    # ------------------------------------------------------------- run_generation

    def test_is_running_returns_true_for_recent_running_generation(self):
        comparison = Comparison(
            generation_status=GenerationStatus.RUNNING,
            generation_started_at=(
                timezone.now() - timedelta(seconds=30)
            ),
        )

        self.assertTrue(_is_running(comparison))

    def test_is_running_returns_false_when_generation_is_not_running(self):
        comparison = Comparison(
            generation_status=GenerationStatus.READY,
            generation_started_at=timezone.now(),
        )

        self.assertFalse(_is_running(comparison))

    def test_is_running_returns_false_without_start_time(self):
        comparison = Comparison(
            generation_status=GenerationStatus.RUNNING,
            generation_started_at=None,
        )

        self.assertFalse(_is_running(comparison))

    def test_is_running_returns_false_after_timeout(self):
        comparison = Comparison(
            generation_status=GenerationStatus.RUNNING,
            generation_started_at=(
                timezone.now() - RUNNING_TIMEOUT - timedelta(seconds=1)
            ),
        )

        self.assertFalse(_is_running(comparison))

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

        self.assertEqual(
            result,
            GenerationStatus.READY,
        )
        self.assertEqual(
            comparison.generation_status,
            GenerationStatus.READY,
        )
        self.assertIsNotNone(
            comparison.generation_started_at,
        )

        mock_get_result.assert_called_once_with(
            user=mock.ANY,
            comparison_id=comparison.pk,
        )

        self.assertEqual(
            mock_notify.call_count,
            2,
        )
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

        self.assertEqual(
            result,
            GenerationStatus.NEEDS_DATA,
        )
        self.assertEqual(
            comparison.generation_status,
            GenerationStatus.NEEDS_DATA,
        )

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

        self.assertEqual(
            result,
            GenerationStatus.FAILED,
        )
        self.assertEqual(
            comparison.generation_status,
            GenerationStatus.FAILED,
        )

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

        self.assertEqual(
            result,
            GenerationStatus.READY,
        )
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

        self.assertEqual(
            result,
            GenerationStatus.RUNNING,
        )
        mock_notify.assert_not_called()

    def test_run_generation_raises_for_missing_comparison(self):
        with self.assertRaises(Comparison.DoesNotExist):
            run_generation(uuid.uuid4())

    # ------------------------------------------------------------ close stale

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

        self.assertEqual(count, 1)
        self.assertFalse(
            ComparisonSession.objects.filter(pk=stale.pk).exists()
        )
        self.assertTrue(
            ComparisonSession.objects.filter(pk=fresh.pk).exists()
        )

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

        self.assertEqual(count, 1)
        self.assertFalse(
            ComparisonSession.objects.filter(pk=room.pk).exists()
        )

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

        self.assertEqual(count, 1)

        room.refresh_from_db()

        self.assertEqual(
            room.status,
            SessionStatus.FINISHED,
        )

    def test_close_stale_rooms_does_not_close_fresh_active_rooms(self):
        room = self._room(
            status=SessionStatus.ACTIVE,
        )

        count = close_stale_rooms()

        self.assertEqual(count, 0)
        self.assertTrue(
            ComparisonSession.objects.filter(pk=room.pk).exists()
        )
