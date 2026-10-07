from __future__ import annotations

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
from apps.comparisons.exceptions import (
    InsufficientDataError,
    NotRoomMemberError,
    RoomClosedError,
    RoomFullError,
    RoomNotFoundError,
    RoomNotReadyError,
)
from apps.comparisons.models import Comparison, ComparisonSession
from apps.comparisons.services.room import (
    RUNNING_TIMEOUT,
    WAITING_ROOM_TIMEOUT,
    _comparison_of,
    _is_running,
    build_room_state,
    close_stale_rooms,
    create_room,
    get_user_room,
    join_room_from_invite,
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

    def test_get_user_room_returns_room_for_member(self):
        room = self._room()

        result = get_user_room(
            room_id=room.pk,
            user=self.user,
        )

        self.assertEqual(result.pk, room.pk)

    def test_get_user_room_raises_for_missing_room(self):
        with self.assertRaises(RoomNotFoundError):
            get_user_room(
                room_id=999999,
                user=self.user,
            )

    def test_get_user_room_raises_for_invalid_room_id(self):
        with self.assertRaises(RoomNotFoundError):
            get_user_room(
                room_id="not-an-id",
                user=self.user,
            )

    def test_get_user_room_raises_for_non_member(self):
        room = self._room()

        with self.assertRaises(NotRoomMemberError):
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

    def test_touch_room_updates_last_seen_at(self):
        old_time = timezone.now() - timedelta(minutes=10)
        room = self._room(last_seen_at=old_time)

        with mock.patch(
            "apps.comparisons.services.room.timezone.now",
            return_value=timezone.now(),
        ):
            from apps.comparisons.services.room import touch_room

            touch_room(room.pk)

        room.refresh_from_db()

        self.assertGreater(room.last_seen_at, old_time)

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

        with self.assertRaises(RoomClosedError):
            regenerate_invite(
                user=self.user,
                room=room,
            )

    def test_join_room_from_invite_rejects_invite_without_session(self):
        invite = self._invite()
        invite.session = None
        invite.save(update_fields=["session"])

        with self.assertRaises(RoomNotFoundError):
            join_room_from_invite(
                invite,
                self.partner,
            )

    def test_join_room_from_invite_rejects_missing_room(self):
        invite = Invite.objects.create(
            inviter=self.user,
            session=None,
            type=InviteType.COMPARISON,
            code="missing-room-code",
            expires_at=timezone.now() + timedelta(minutes=5),
        )

        with self.assertRaises(RoomNotFoundError):
            join_room_from_invite(
                invite,
                self.partner,
            )

    def test_join_room_from_invite_rejects_finished_room(self):
        room = self._room(
            status=SessionStatus.FINISHED,
        )
        invite = self._invite(room=room)

        with self.assertRaises(RoomClosedError):
            join_room_from_invite(
                invite,
                self.partner,
            )

    def test_join_room_from_invite_rejects_active_room(self):
        room = self._room(
            status=SessionStatus.ACTIVE,
        )
        invite = self._invite(room=room)

        with self.assertRaises(RoomFullError):
            join_room_from_invite(
                invite,
                self.partner,
            )

    def test_join_room_from_invite_rejects_full_waiting_room(self):
        room = self._room()
        room.users.add(self.partner)

        invite = self._invite(room=room)

        other = User.objects.create_user(
            email="d@x.com",
            username="d",
            password="pw",
        )

        with self.assertRaises(RoomFullError):
            join_room_from_invite(
                invite,
                other,
            )

    @mock.patch(
        "apps.comparisons.services.room.notify_room"
    )
    def test_join_room_from_invite_adds_user_and_activates_room(
        self,
        mock_notify,
    ):
        room = self._room()
        invite = self._invite(room=room)

        with self.captureOnCommitCallbacks(execute=True):
            result = join_room_from_invite(
                invite,
                self.partner,
            )

        room.refresh_from_db()

        self.assertEqual(result.pk, room.pk)
        self.assertEqual(
            room.status,
            SessionStatus.ACTIVE,
        )
        self.assertTrue(
            room.users.filter(pk=self.partner.pk).exists()
        )
        self.assertEqual(
            Comparison.objects.filter(session=room).count(),
            1,
        )

        mock_notify.assert_called_once_with(
            room.pk,
            reason="partner_joined",
        )

    @mock.patch(
        "apps.comparisons.services.room.notify_room"
    )
    def test_join_room_from_invite_creates_comparison(
        self,
        mock_notify,
    ):
        room = self._room()
        invite = self._invite(room=room)

        with self.captureOnCommitCallbacks(execute=True):
            join_room_from_invite(
                invite,
                self.partner,
            )

        comparison = Comparison.objects.get(
            session=room,
        )

        self.assertEqual(
            comparison.session_id,
            room.pk,
        )

    def test_request_generation_rejects_waiting_room(self):
        room = self._room(
            status=SessionStatus.WAITING,
        )

        with self.assertRaises(RoomNotReadyError):
            request_generation(room=room)

    def test_request_generation_rejects_room_without_comparison(self):
        room = self._room(
            status=SessionStatus.ACTIVE,
        )

        with self.assertRaises(RoomNotReadyError):
            request_generation(room=room)

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
            run_generation(999999)

    def test_close_stale_rooms_deletes_old_waiting_rooms(self):
        stale = self._room(
            last_seen_at=(
                timezone.now()
                - WAITING_ROOM_TIMEOUT
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
            - WAITING_ROOM_TIMEOUT
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

    def test_close_stale_rooms_does_not_delete_active_rooms(self):
        room = self._room(
            status=SessionStatus.ACTIVE,
            last_seen_at=(
                timezone.now()
                - WAITING_ROOM_TIMEOUT
                - timedelta(days=1)
            ),
        )

        count = close_stale_rooms()

        self.assertEqual(count, 0)
        self.assertTrue(
            ComparisonSession.objects.filter(pk=room.pk).exists()
        )
