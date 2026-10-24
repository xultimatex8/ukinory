from datetime import timedelta
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.common.enums import SessionStatus, SessionType
from apps.common.exceptions import (
    InvalidSessionStateError,
    NotSessionMemberError,
    PartnerNotJoinedError,
    SessionFinishedError,
    SessionNotFoundError,
)
from apps.common.models import Session
from apps.common.services.sessions import (
    MAX_PARTICIPANTS,
    STALE_TIMEOUT,
    LeaveOutcome,
    StaleOutcome,
    _cutoff,
    activate_session,
    close_stale_session,
    close_stale_sessions,
    ensure_session_active,
    get_user_session,
    is_stale,
    leave_session,
    lock_session,
    stale_sessions,
    touch_session,
)

User = get_user_model()


class SessionLifecycleTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="a@example.com",
            username="a",
            password="pw",
        )
        self.partner = User.objects.create_user(
            email="b@example.com",
            username="b",
            password="pw",
        )
        self.session = Session.objects.create(
            session_type=SessionType.COMPARISON_SESSION,
        )
        self.session.users.add(self.user)

    def _make_stale(self, session=None, status=SessionStatus.WAITING):
        session = session or self.session
        session.status = status
        session.last_seen_at = timezone.now() - STALE_TIMEOUT - timedelta(
            seconds=1
        )
        session.save(update_fields=["status", "last_seen_at"])
        return session

    def _make_recent(self, session=None, status=SessionStatus.WAITING):
        session = session or self.session
        session.status = status
        session.last_seen_at = timezone.now()
        session.save(update_fields=["status", "last_seen_at"])
        return session


class GetUserSessionTests(SessionLifecycleTests):
    def test_returns_session_for_member(self):
        result = get_user_session(
            Session,
            session_id=self.session.pk,
            user=self.user,
        )

        self.assertEqual(result.pk, self.session.pk)

    def test_accepts_custom_queryset(self):
        result = get_user_session(
            Session,
            session_id=self.session.pk,
            user=self.user,
            queryset=Session.objects.filter(
                session_type=SessionType.COMPARISON_SESSION
            ),
        )

        self.assertEqual(result.pk, self.session.pk)

    def test_rejects_non_member(self):
        with self.assertRaises(NotSessionMemberError):
            get_user_session(
                Session,
                session_id=self.session.pk,
                user=self.partner,
            )

    def test_raises_when_session_does_not_exist(self):
        with self.assertRaises(SessionNotFoundError):
            get_user_session(
                Session,
                session_id=999999,
                user=self.user,
            )

    def test_raises_for_invalid_session_id(self):
        with self.assertRaises(SessionNotFoundError):
            get_user_session(
                Session,
                session_id="not-an-id",
                user=self.user,
            )


class LockSessionTests(SessionLifecycleTests):
    def test_returns_existing_session(self):
        result = lock_session(Session, self.session.pk)

        self.assertEqual(result.pk, self.session.pk)

    def test_raises_when_session_does_not_exist(self):
        with self.assertRaises(SessionNotFoundError):
            lock_session(Session, 999999)

    def test_raises_for_invalid_id(self):
        with self.assertRaises(SessionNotFoundError):
            lock_session(Session, "invalid")


class TouchSessionTests(SessionLifecycleTests):
    def test_updates_last_seen_at(self):
        old_time = timezone.now() - timedelta(minutes=5)
        Session.objects.filter(pk=self.session.pk).update(
            last_seen_at=old_time
        )

        touch_session(self.session.pk)

        self.session.refresh_from_db()
        self.assertIsNotNone(self.session.last_seen_at)
        self.assertGreater(self.session.last_seen_at, old_time)


class StalenessTests(SessionLifecycleTests):
    def test_cutoff_uses_stale_timeout(self):
        now = timezone.now()

        self.assertEqual(_cutoff(now), now - STALE_TIMEOUT)
        self.assertEqual(STALE_TIMEOUT, timedelta(minutes=2))

    def test_waiting_session_becomes_stale(self):
        self._make_stale(status=SessionStatus.WAITING)

        self.assertTrue(is_stale(self.session))

    def test_active_session_becomes_stale(self):
        self._make_stale(status=SessionStatus.ACTIVE)

        self.assertTrue(is_stale(self.session))

    def test_recent_session_is_not_stale(self):
        self._make_recent(status=SessionStatus.WAITING)

        self.assertFalse(is_stale(self.session))

    def test_finished_session_is_not_stale(self):
        self._make_stale(status=SessionStatus.FINISHED)

        self.assertFalse(is_stale(self.session))

    def test_uses_created_at_when_last_seen_is_none(self):
        old_time = timezone.now() - timedelta(minutes=5)
        Session.objects.filter(pk=self.session.pk).update(
            last_seen_at=None,
            created_at=old_time,
        )
        self.session.refresh_from_db()

        self.assertTrue(is_stale(self.session))

    def test_recent_created_at_is_not_stale_without_last_seen(self):
        Session.objects.filter(pk=self.session.pk).update(
            last_seen_at=None,
            created_at=timezone.now(),
        )
        self.session.refresh_from_db()

        self.assertFalse(is_stale(self.session))

    def test_stale_sessions_returns_only_stale_live_sessions(self):
        stale = self._make_stale()
        recent = Session.objects.create(
            session_type=SessionType.COMPARISON_SESSION,
            status=SessionStatus.WAITING,
            last_seen_at=timezone.now(),
        )
        finished = Session.objects.create(
            session_type=SessionType.COMPARISON_SESSION,
            status=SessionStatus.FINISHED,
            last_seen_at=timezone.now() - timedelta(minutes=5),
        )

        ids = set(stale_sessions(Session).values_list("pk", flat=True))

        self.assertIn(stale.pk, ids)
        self.assertNotIn(recent.pk, ids)
        self.assertNotIn(finished.pk, ids)


class CloseStaleSessionTests(SessionLifecycleTests):
    def test_missing_session_returns_not_stale(self):
        result = close_stale_session(999999)

        self.assertEqual(result, StaleOutcome.NOT_STALE)

    def test_recent_session_returns_not_stale(self):
        self._make_recent()

        result = close_stale_session(self.session.pk)

        self.assertEqual(result, StaleOutcome.NOT_STALE)
        self.assertTrue(
            Session.objects.filter(pk=self.session.pk).exists()
        )

    def test_stale_waiting_session_is_deleted(self):
        self._make_stale(status=SessionStatus.WAITING)
        session_id = self.session.pk

        result = close_stale_session(session_id)

        self.assertEqual(result, StaleOutcome.DELETED)
        self.assertFalse(
            Session.objects.filter(pk=session_id).exists()
        )

    def test_stale_active_session_is_finished(self):
        self._make_stale(status=SessionStatus.ACTIVE)

        result = close_stale_session(self.session.pk)

        self.assertEqual(result, StaleOutcome.FINISHED)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, SessionStatus.FINISHED)

    def test_calls_callback_after_deleting_session(self):
        self._make_stale(status=SessionStatus.WAITING)
        callback = Mock()
        session_id = self.session.pk

        with self.captureOnCommitCallbacks(execute=True):
            result = close_stale_session(
                session_id,
                on_closed=callback,
            )

        self.assertEqual(result, StaleOutcome.DELETED)
        callback.assert_called_once_with(
            session_id,
            StaleOutcome.DELETED,
        )

    def test_calls_callback_after_finishing_session(self):
        self._make_stale(status=SessionStatus.ACTIVE)
        callback = Mock()
        session_id = self.session.pk

        with self.captureOnCommitCallbacks(execute=True):
            result = close_stale_session(
                session_id,
                on_closed=callback,
            )

        self.assertEqual(result, StaleOutcome.FINISHED)
        callback.assert_called_once_with(
            session_id,
            StaleOutcome.FINISHED,
        )

    def test_does_not_call_callback_for_recent_session(self):
        self._make_recent()
        callback = Mock()

        with self.captureOnCommitCallbacks(execute=True):
            result = close_stale_session(
                self.session.pk,
                on_closed=callback,
            )

        self.assertEqual(result, StaleOutcome.NOT_STALE)
        callback.assert_not_called()

    def test_does_not_require_callback(self):
        self._make_stale(status=SessionStatus.ACTIVE)

        with self.captureOnCommitCallbacks(execute=True):
            result = close_stale_session(self.session.pk)

        self.assertEqual(result, StaleOutcome.FINISHED)


class CloseStaleSessionsTests(SessionLifecycleTests):
    def test_closes_stale_sessions_and_returns_count(self):
        waiting = self._make_stale(status=SessionStatus.WAITING)

        active = Session.objects.create(
            session_type=SessionType.COMPARISON_SESSION,
            status=SessionStatus.ACTIVE,
            last_seen_at=timezone.now() - timedelta(minutes=5),
        )
        recent = Session.objects.create(
            session_type=SessionType.COMPARISON_SESSION,
            status=SessionStatus.WAITING,
            last_seen_at=timezone.now(),
        )

        result = close_stale_sessions()

        self.assertEqual(result, 2)
        self.assertFalse(
            Session.objects.filter(pk=waiting.pk).exists()
        )
        active.refresh_from_db()
        recent.refresh_from_db()
        self.assertEqual(active.status, SessionStatus.FINISHED)
        self.assertEqual(recent.status, SessionStatus.WAITING)

    def test_returns_zero_when_nothing_is_stale(self):
        self._make_recent()

        self.assertEqual(close_stale_sessions(), 0)

    def test_passes_callback_to_closed_sessions(self):
        self._make_stale(status=SessionStatus.ACTIVE)
        callback = Mock()

        with self.captureOnCommitCallbacks(execute=True):
            result = close_stale_sessions(on_closed=callback)

        self.assertEqual(result, 1)
        callback.assert_called_once_with(
            self.session.pk,
            StaleOutcome.FINISHED,
        )


class EnsureSessionActiveTests(SessionLifecycleTests):
    def test_raises_when_already_finished(self):
        self.session.status = SessionStatus.FINISHED
        self.session.save(update_fields=["status"])

        with self.assertRaises(SessionFinishedError):
            ensure_session_active(self.session)

    def test_does_not_raise_when_active_and_recent(self):
        self._make_recent(status=SessionStatus.ACTIVE)

        ensure_session_active(self.session)

    def test_stale_waiting_session_is_deleted_and_raises(self):
        self._make_stale(status=SessionStatus.WAITING)
        session_id = self.session.pk

        with self.assertRaises(SessionFinishedError):
            ensure_session_active(self.session)

        self.assertFalse(
            Session.objects.filter(pk=session_id).exists()
        )

    def test_stale_active_session_is_finished_and_raises(self):
        self._make_stale(status=SessionStatus.ACTIVE)

        with self.assertRaises(SessionFinishedError):
            ensure_session_active(self.session)

        self.session.refresh_from_db()
        self.assertEqual(self.session.status, SessionStatus.FINISHED)

    def test_passes_callback_when_closing_stale_session(self):
        self._make_stale(status=SessionStatus.ACTIVE)
        callback = Mock()

        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(SessionFinishedError):
                ensure_session_active(
                    self.session,
                    on_closed=callback,
                )

        callback.assert_called_once_with(
            self.session.pk,
            StaleOutcome.FINISHED,
        )


class ActivateSessionTests(SessionLifecycleTests):
    def test_returns_session_if_already_active(self):
        self._make_recent(status=SessionStatus.ACTIVE)

        result = activate_session(Session, self.session.pk)

        self.assertEqual(result.pk, self.session.pk)

    def test_rejects_finished_session(self):
        self.session.status = SessionStatus.FINISHED
        self.session.save(update_fields=["status"])

        with self.assertRaises(InvalidSessionStateError):
            activate_session(Session, self.session.pk)

    def test_rejects_session_without_partner(self):
        with self.assertRaises(PartnerNotJoinedError):
            activate_session(Session, self.session.pk)

        self.session.refresh_from_db()
        self.assertEqual(self.session.status, SessionStatus.WAITING)

    def test_activates_session_with_two_participants(self):
        self.session.users.add(self.partner)

        result = activate_session(Session, self.session.pk)

        self.assertEqual(result.status, SessionStatus.ACTIVE)
        self.assertIsNotNone(result.last_seen_at)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, SessionStatus.ACTIVE)

    def test_calls_prepare_before_activation(self):
        self.session.users.add(self.partner)
        observed_statuses = []

        def prepare(session):
            observed_statuses.append(session.status)

        activate_session(
            Session,
            self.session.pk,
            prepare=prepare,
        )

        self.assertEqual(observed_statuses[0], SessionStatus.WAITING)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, SessionStatus.ACTIVE)

    def test_notifies_after_commit(self):
        self.session.users.add(self.partner)
        notify = Mock()

        with self.captureOnCommitCallbacks(execute=True):
            result = activate_session(
                Session,
                self.session.pk,
                notify=notify,
            )

        notify.assert_called_once()
        notified_session = notify.call_args.args[0]
        self.assertEqual(notified_session.pk, result.pk)
        self.assertEqual(notified_session.status, SessionStatus.ACTIVE)

    def test_does_not_notify_when_callback_not_provided(self):
        self.session.users.add(self.partner)

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            activate_session(Session, self.session.pk)

        self.assertEqual(callbacks, [])

    def test_prepare_error_prevents_activation(self):
        self.session.users.add(self.partner)
        prepare = Mock(side_effect=RuntimeError("Preparation failed"))

        with self.assertRaisesRegex(RuntimeError, "Preparation failed"):
            activate_session(
                Session,
                self.session.pk,
                prepare=prepare,
            )

        self.session.refresh_from_db()
        self.assertEqual(self.session.status, SessionStatus.WAITING)

    def test_requires_configured_number_of_participants(self):
        self.assertEqual(MAX_PARTICIPANTS, 2)
        self.session.users.add(self.partner)

        result = activate_session(Session, self.session.pk)

        self.assertEqual(result.status, SessionStatus.ACTIVE)


class LeaveSessionTests(SessionLifecycleTests):
    def test_outcomes_have_stable_values(self):
        self.assertEqual(
            {outcome.value for outcome in LeaveOutcome},
            {"already_finished", "left", "deleted", "finished"},
        )

    def test_raises_when_session_does_not_exist(self):
        with self.assertRaises(SessionNotFoundError):
            leave_session(Session, 999999, self.user)

    def test_raises_for_invalid_session_id(self):
        with self.assertRaises(SessionNotFoundError):
            leave_session(Session, "invalid", self.user)

    def test_finished_session_returns_already_finished(self):
        self._make_recent(status=SessionStatus.FINISHED)

        result = leave_session(Session, self.session.pk, self.user)

        self.assertEqual(result, LeaveOutcome.ALREADY_FINISHED)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, SessionStatus.FINISHED)
        self.assertTrue(self.session.users.filter(pk=self.user.pk).exists())

    def test_finished_session_does_not_check_membership(self):
        self._make_recent(status=SessionStatus.FINISHED)

        result = leave_session(Session, self.session.pk, self.partner)

        self.assertEqual(result, LeaveOutcome.ALREADY_FINISHED)
        self.assertTrue(
            Session.objects.filter(pk=self.session.pk).exists()
        )

    def test_non_member_cannot_leave_waiting_session(self):
        self._make_recent(status=SessionStatus.WAITING)

        with self.assertRaises(NotSessionMemberError):
            leave_session(Session, self.session.pk, self.partner)

        self.session.refresh_from_db()
        self.assertEqual(self.session.status, SessionStatus.WAITING)
        self.assertEqual(self.session.users.count(), 1)

    def test_non_member_cannot_leave_active_session(self):
        self.session.users.add(self.partner)
        self._make_recent(status=SessionStatus.ACTIVE)
        outsider = User.objects.create_user(
            email="c@example.com",
            username="c",
            password="pw",
        )

        with self.assertRaises(NotSessionMemberError):
            leave_session(Session, self.session.pk, outsider)

        self.session.refresh_from_db()
        self.assertEqual(self.session.status, SessionStatus.ACTIVE)
        self.assertEqual(self.session.users.count(), 2)

    def test_last_user_leaving_waiting_session_deletes_it(self):
        self._make_recent(status=SessionStatus.WAITING)
        session_id = self.session.pk

        result = leave_session(Session, session_id, self.user)

        self.assertEqual(result, LeaveOutcome.DELETED)
        self.assertFalse(Session.objects.filter(pk=session_id).exists())

    def test_waiting_session_with_remaining_user_is_kept(self):
        self.session.users.add(self.partner)
        self._make_recent(status=SessionStatus.WAITING)

        result = leave_session(Session, self.session.pk, self.user)

        self.assertEqual(result, LeaveOutcome.LEFT)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, SessionStatus.WAITING)
        self.assertEqual(
            list(self.session.users.values_list("pk", flat=True)),
            [self.partner.pk],
        )

    def test_active_session_is_finished_when_a_member_leaves(self):
        self.session.users.add(self.partner)
        self._make_recent(status=SessionStatus.ACTIVE)

        result = leave_session(Session, self.session.pk, self.user)

        self.assertEqual(result, LeaveOutcome.FINISHED)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, SessionStatus.FINISHED)

    def test_active_session_keeps_its_members_when_finished(self):
        self.session.users.add(self.partner)
        self._make_recent(status=SessionStatus.ACTIVE)

        leave_session(Session, self.session.pk, self.user)

        self.assertEqual(self.session.users.count(), 2)
