from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone

from apps.common.enums import SessionStatus
from apps.common.exceptions import (
    InvalidSessionStateError,
    NotSessionMemberError,
    SessionFinishedError,
    SessionNotFoundError,
)
from apps.swipe_sessions.models import SwipeSession
from apps.swipe_sessions.services import session as session_module
from apps.swipe_sessions.services.session import (
    _notify_closed,
    close_stale_swipe_sessions,
    create_swipe_session,
    end_swipe_session,
    ensure_session_active,
    get_user_swipe_session,
    start_swipe_session,
)
from types import SimpleNamespace
from apps.common.enums import SessionType, SwipeSessionType
from apps.common.services.sessions import StaleOutcome
from apps.swipe_sessions.models import SwipeSessionCandidate


@pytest.fixture
def swipe_session(db):
    return SwipeSession.objects.create(
        type="solo", session_type=SessionType.SWIPE_SESSION
    )



class TestGetUserSwipeSession:
    @pytest.mark.django_db
    def test_returns_session_for_member(
        self,
        user,
        swipe_session,
    ):
        swipe_session.users.add(user)

        result = get_user_swipe_session(
            session_id=swipe_session.pk,
            user=user,
        )

        assert result == swipe_session

    @pytest.mark.django_db
    def test_raises_when_session_does_not_exist(self, user):
        with pytest.raises(SessionNotFoundError):
            get_user_swipe_session(
                session_id=999999,
                user=user,
            )

    @pytest.mark.django_db
    def test_raises_when_user_is_not_a_member(
        self,
        user,
        swipe_session,
    ):
        with pytest.raises(NotSessionMemberError):
            get_user_swipe_session(
                session_id=swipe_session.pk,
                user=user,
            )


class TestCreateSwipeSession:
    @pytest.mark.django_db
    def test_creates_session_with_type_and_user(
        self,
        user,
    ):
        session = create_swipe_session(
            user=user,
            session_type="solo",
        )

        assert session.type == "solo"
        assert session.users.filter(pk=user.pk).exists()

    @pytest.mark.django_db
    def test_creates_session_with_default_status(
        self,
        user,
    ):
        session = create_swipe_session(
            user=user,
            session_type="solo",
        )

        assert session.status == SessionStatus.WAITING


class TestStartSwipeSession:
    @pytest.mark.django_db
    def test_starts_waiting_session(
        self,
        user,
        swipe_session,
    ):
        assert swipe_session.status == SessionStatus.WAITING

        with patch(
            "apps.swipe_sessions.services.session.fill_candidate_pool"
        ) as fill_pool:
            result = start_swipe_session(
                user=user,
                session=swipe_session,
            )

        result.refresh_from_db()

        assert result == swipe_session
        assert result.status == SessionStatus.ACTIVE
        assert result.last_seen_at is not None

        fill_pool.assert_called_once_with(
            session=swipe_session,
            user=user,
        )

    @pytest.mark.django_db
    @pytest.mark.parametrize(
        "status",
        [
            SessionStatus.ACTIVE,
            SessionStatus.FINISHED,
        ],
    )
    def test_rejects_session_that_has_already_started_or_finished(
        self,
        user,
        swipe_session,
        status,
    ):
        swipe_session.status = status
        swipe_session.save(update_fields=["status"])

        with pytest.raises(
            InvalidSessionStateError,
            match="Swipe session has already started or finished.",
        ):
            start_swipe_session(
                user=user,
                session=swipe_session,
            )

        swipe_session.refresh_from_db()

        assert swipe_session.status == status

    @pytest.mark.django_db
    def test_fills_candidate_pool(
        self,
        user,
        swipe_session,
    ):
        with patch(
            "apps.swipe_sessions.services.session.fill_candidate_pool"
        ) as fill_pool:
            start_swipe_session(
                user=user,
                session=swipe_session,
            )

        fill_pool.assert_called_once_with(
            session=swipe_session,
            user=user,
        )


class TestEndSwipeSession:
    @pytest.mark.django_db
    def test_ends_active_session(
        self,
        user,
        swipe_session,
    ):
        swipe_session.users.add(user)

        swipe_session.status = SessionStatus.ACTIVE
        swipe_session.save(update_fields=["status"])

        summary = MagicMock()

        with patch(
            "apps.swipe_sessions.services.session.export_watchlist_csv",
            return_value=summary,
        ) as export_watchlist:
            result = end_swipe_session(
                user=user,
                session=swipe_session,
            )

        swipe_session.refresh_from_db()

        assert result == summary
        assert swipe_session.status == SessionStatus.FINISHED

        export_watchlist.assert_called_once_with(
            user=user,
            session=swipe_session,
        )

    @pytest.mark.django_db
    @pytest.mark.parametrize(
        "status",
        [
            SessionStatus.WAITING,
            SessionStatus.FINISHED,
        ],
    )
    def test_rejects_session_that_is_not_active(
        self,
        user,
        swipe_session,
        status,
    ):
        swipe_session.status = status
        swipe_session.save(update_fields=["status"])

        with pytest.raises(
            InvalidSessionStateError,
            match="Swipe session has not started yet.",
        ):
            end_swipe_session(
                user=user,
                session=swipe_session,
            )

        swipe_session.refresh_from_db()

        assert swipe_session.status == status


class TestEnsureSessionActive:
    @pytest.mark.django_db
    def test_allows_active_session_with_recent_last_seen(
        self,
        swipe_session,
    ):
        swipe_session.status = SessionStatus.ACTIVE
        swipe_session.last_seen_at = timezone.now() - timedelta(minutes=1)
        swipe_session.save(update_fields=["status", "last_seen_at"])

        ensure_session_active(swipe_session)

        swipe_session.refresh_from_db()

        assert swipe_session.status == SessionStatus.ACTIVE

    @pytest.mark.django_db
    def test_allows_waiting_session_with_recent_created_at(
        self,
        swipe_session,
    ):
        swipe_session.status = SessionStatus.WAITING
        swipe_session.last_seen_at = None
        swipe_session.created_at = timezone.now() - timedelta(minutes=1)
        swipe_session.save(
            update_fields=["status", "last_seen_at", "created_at"]
        )

        ensure_session_active(swipe_session)

        swipe_session.refresh_from_db()

        assert swipe_session.status == SessionStatus.WAITING

    @pytest.mark.django_db
    def test_raises_for_finished_session(
        self,
        swipe_session,
    ):
        swipe_session.status = SessionStatus.FINISHED
        swipe_session.save(update_fields=["status"])

        with pytest.raises(SessionFinishedError):
            ensure_session_active(swipe_session)

        swipe_session.refresh_from_db()

        assert swipe_session.status == SessionStatus.FINISHED

    @pytest.mark.django_db
    def test_finishes_stale_active_session(
        self,
        user,
        swipe_session,
        django_capture_on_commit_callbacks,
    ):
        swipe_session.users.add(user)

        swipe_session.status = SessionStatus.ACTIVE
        swipe_session.last_seen_at = timezone.now() - timedelta(minutes=3)
        swipe_session.save(update_fields=["status", "last_seen_at"])

        with patch(
            "apps.swipe_sessions.services.session.notify_session"
        ) as notify:
            with django_capture_on_commit_callbacks(execute=True):
                with pytest.raises(SessionFinishedError):
                    ensure_session_active(swipe_session)

        swipe_session.refresh_from_db()

        assert swipe_session.status == SessionStatus.FINISHED

        notify.assert_called_once_with(
            swipe_session.pk,
            event="session.updated",
            reason="ended",
        )

    @pytest.mark.django_db
    def test_deletes_stale_waiting_session_using_created_at(
        self,
        user,
        swipe_session,
    ):
        swipe_session.users.add(user)

        swipe_session.status = SessionStatus.WAITING
        swipe_session.last_seen_at = None
        swipe_session.created_at = timezone.now() - timedelta(minutes=3)
        swipe_session.save(
            update_fields=["status", "last_seen_at", "created_at"]
        )
        session_id = swipe_session.pk

        with pytest.raises(SessionFinishedError):
            ensure_session_active(swipe_session)

        assert not SwipeSession.objects.filter(pk=session_id).exists()


class TestCloseStaleSwipeSessions:
    @pytest.mark.django_db
    def test_deletes_stale_waiting_and_finishes_stale_active(
        self,
        user,
        django_capture_on_commit_callbacks,
    ):
        stale_waiting = create_swipe_session(user, "solo")
        stale_active = create_swipe_session(user, "solo")
        fresh = create_swipe_session(user, "solo")

        old = timezone.now() - timedelta(minutes=3)
        SwipeSession.objects.filter(pk=stale_waiting.pk).update(last_seen_at=old)
        SwipeSession.objects.filter(pk=stale_active.pk).update(
            status=SessionStatus.ACTIVE,
            last_seen_at=old,
        )
        SwipeSession.objects.filter(pk=fresh.pk).update(
            last_seen_at=timezone.now()
        )

        with patch(
            "apps.swipe_sessions.services.session.notify_session"
        ) as notify:
            with django_capture_on_commit_callbacks(execute=True):
                closed = close_stale_swipe_sessions()

        assert closed == 2
        assert not SwipeSession.objects.filter(pk=stale_waiting.pk).exists()

        stale_active.refresh_from_db()
        fresh.refresh_from_db()

        assert stale_active.status == SessionStatus.FINISHED
        assert fresh.status == SessionStatus.WAITING

        notify.assert_called_once_with(
            stale_active.pk,
            event="session.updated",
            reason="ended",
        )


def make_paired_session(*users, status=SessionStatus.ACTIVE):
    session = SwipeSession.objects.create(
        type=SwipeSessionType.PAIRED,
        session_type=SessionType.SWIPE_SESSION,
        status=status,
    )
    session.users.add(*users)
    return session


def add_candidate(session, movie, position=1, score=0.5):
    return SwipeSessionCandidate.objects.create(
        session=session, movie=movie, score=score, position=position
    )


MODULE = "apps.swipe_sessions.services.session"


@pytest.mark.django_db
class TestCreateSwipeSessionDetails:
    def test_the_generic_session_type_is_swipe(self, user):
        session = create_swipe_session(user, "solo")

        assert session.session_type == SessionType.SWIPE_SESSION

    def test_a_paired_type_is_stored(self, user):
        session = create_swipe_session(user, SwipeSessionType.PAIRED)

        assert session.type == SwipeSessionType.PAIRED

    def test_the_creator_is_the_only_member(self, user):
        session = create_swipe_session(user, "solo")

        assert list(session.users.all()) == [user]


@pytest.mark.django_db
class TestStartPairedSession:
    def test_delegates_to_the_shared_activation_with_the_paired_pool_filler(
        self, user, another_user
    ):
        session = make_paired_session(user, another_user, status=SessionStatus.WAITING)

        with patch(f"{MODULE}.activate_session") as activate:
            result = start_swipe_session(user, session)

        assert result is activate.return_value
        args, kwargs = activate.call_args
        assert args == (SwipeSession, session.pk)
        assert kwargs["prepare"] is session_module.fill_paired_candidate_pool

    def test_the_session_is_notified_once_it_has_started(self, user, another_user):
        session = make_paired_session(user, another_user, status=SessionStatus.WAITING)

        with patch(f"{MODULE}.activate_session") as activate, patch(
            f"{MODULE}.notify_session"
        ) as notify:
            start_swipe_session(user, session)
            activate.call_args.kwargs["notify"](SimpleNamespace(pk=9))

        notify.assert_called_once_with(9, event="session.updated", reason="started")

    def test_the_solo_flow_is_not_used(self, user, another_user):
        session = make_paired_session(user, another_user, status=SessionStatus.WAITING)

        with patch(f"{MODULE}.activate_session"), patch(
            f"{MODULE}.fill_candidate_pool"
        ) as fill_solo:
            start_swipe_session(user, session)

        fill_solo.assert_not_called()


@pytest.mark.django_db
class TestStartSoloSessionDetails:
    def test_a_failing_pool_fill_rolls_the_start_back(self, user, swipe_session):
        with patch(f"{MODULE}.fill_candidate_pool", side_effect=RuntimeError("boom")):
            with pytest.raises(RuntimeError):
                start_swipe_session(user, swipe_session)

        swipe_session.refresh_from_db()
        assert swipe_session.status == SessionStatus.WAITING

    def test_the_session_is_stamped_as_just_seen(self, user, swipe_session):
        with patch(f"{MODULE}.fill_candidate_pool"):
            start_swipe_session(user, swipe_session)

        swipe_session.refresh_from_db()
        assert timezone.now() - swipe_session.last_seen_at < timedelta(minutes=1)


@pytest.mark.django_db
class TestEndPairedSession:
    def test_an_active_session_is_finished_and_exported_for_the_ending_user(
        self, user, another_user, django_capture_on_commit_callbacks
    ):
        session = make_paired_session(user, another_user)
        summary = MagicMock()

        with patch(f"{MODULE}.export_watchlist_csv", return_value=summary) as export, patch(
            f"{MODULE}.notify_session"
        ) as notify:
            with django_capture_on_commit_callbacks(execute=True):
                result = end_swipe_session(another_user, session)

        session.refresh_from_db()
        assert result is summary
        assert session.status == SessionStatus.FINISHED
        export.assert_called_once()
        assert export.call_args.kwargs["user"] == another_user
        assert export.call_args.kwargs["session"].pk == session.pk
        notify.assert_called_once_with(
            session.pk, event="session.updated", reason="ended"
        )

    def test_a_session_that_never_started_can_also_be_ended(self, user, another_user):
        session = make_paired_session(user, another_user, status=SessionStatus.WAITING)

        with patch(f"{MODULE}.export_watchlist_csv"), patch(f"{MODULE}.notify_session"):
            end_swipe_session(user, session)

        session.refresh_from_db()
        assert session.status == SessionStatus.FINISHED

    def test_ending_a_finished_session_only_exports_again(
        self, user, another_user, django_capture_on_commit_callbacks
    ):
        session = make_paired_session(user, another_user, status=SessionStatus.FINISHED)
        summary = MagicMock()

        with patch(f"{MODULE}.export_watchlist_csv", return_value=summary) as export, patch(
            f"{MODULE}.notify_session"
        ) as notify:
            with django_capture_on_commit_callbacks(execute=True) as callbacks:
                result = end_swipe_session(user, session)

        assert result is summary
        assert callbacks == []
        notify.assert_not_called()
        assert export.call_args.kwargs["user"] == user


@pytest.mark.django_db
class TestEndSoloSessionDetails:
    def test_a_session_without_members_is_finished_without_an_export(self, swipe_session):
        SwipeSession.objects.filter(pk=swipe_session.pk).update(status=SessionStatus.ACTIVE)
        swipe_session.refresh_from_db()

        with patch(f"{MODULE}.export_watchlist_csv") as export:
            result = end_swipe_session(None, swipe_session)

        swipe_session.refresh_from_db()
        assert result is None
        assert swipe_session.status == SessionStatus.FINISHED
        export.assert_not_called()

    def test_solo_sessions_do_not_notify_anyone(
        self, user, swipe_session, django_capture_on_commit_callbacks
    ):
        swipe_session.users.add(user)
        SwipeSession.objects.filter(pk=swipe_session.pk).update(status=SessionStatus.ACTIVE)
        swipe_session.refresh_from_db()

        with patch(f"{MODULE}.export_watchlist_csv"), patch(
            f"{MODULE}.notify_session"
        ) as notify:
            with django_capture_on_commit_callbacks(execute=True):
                end_swipe_session(user, swipe_session)

        notify.assert_not_called()

    def test_the_export_is_made_for_a_member_of_the_session(
        self, user, another_user, swipe_session
    ):
        swipe_session.users.add(user, another_user)
        SwipeSession.objects.filter(pk=swipe_session.pk).update(status=SessionStatus.ACTIVE)
        swipe_session.refresh_from_db()

        with patch(f"{MODULE}.export_watchlist_csv") as export:
            end_swipe_session(user, swipe_session)

        assert export.call_args.kwargs["user"] in {user, another_user}


class TestNotifyClosed:
    def test_a_finished_session_is_announced_as_ended(self):
        with patch(f"{MODULE}.notify_session") as notify:
            _notify_closed(5, StaleOutcome.FINISHED)

        notify.assert_called_once_with(5, event="session.updated", reason="ended")

    @pytest.mark.parametrize(
        "outcome", [o for o in StaleOutcome if o is not StaleOutcome.FINISHED]
    )
    def test_other_outcomes_are_not_announced(self, outcome):
        with patch(f"{MODULE}.notify_session") as notify:
            _notify_closed(5, outcome)

        notify.assert_not_called()


class TestStaleSessionWiring:
    def test_ensure_session_active_reports_closures_through_notify_closed(self):
        session = SimpleNamespace(pk=1)

        with patch(f"{MODULE}._ensure_session_active") as ensure:
            ensure_session_active(session)

        ensure.assert_called_once_with(session, on_closed=_notify_closed)

    def test_closing_stale_sessions_reports_closures_through_notify_closed(self):
        with patch(f"{MODULE}.close_stale_sessions", return_value=3) as close:
            result = close_stale_swipe_sessions()

        assert result == 3
        close.assert_called_once_with(SwipeSession, on_closed=_notify_closed)
