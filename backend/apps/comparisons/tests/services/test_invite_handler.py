from __future__ import annotations

from unittest import mock

from django.test import TestCase

from apps.comparisons.models import ComparisonSession
from apps.comparisons.services.invite_handler import (
    accept_comparison_invite,
)


class AcceptComparisonInviteTests(TestCase):
    @mock.patch(
        "apps.comparisons.services.invite_handler.notify_room"
    )
    @mock.patch(
        "apps.comparisons.services.invite_handler.join_session_from_invite"
    )
    def test_accepts_invite_and_returns_session(
        self,
        mock_join,
        mock_notify_room,
    ):
        invite = object()
        user = object()
        expected_room = mock.Mock(spec=ComparisonSession)
        expected_room.pk = 123

        mock_join.return_value = expected_room

        result = accept_comparison_invite(
            invite,
            user,
        )

        self.assertIs(result, expected_room)
        mock_join.assert_called_once()

        call_args = mock_join.call_args
        self.assertEqual(
            call_args.args,
            (invite, user, ComparisonSession),
        )

        notify = call_args.kwargs["notify"]
        notify(expected_room)

        mock_notify_room.assert_called_once_with(
            123,
            reason="partner_joined",
        )

    @mock.patch(
        "apps.comparisons.services.invite_handler.join_session_from_invite"
    )
    def test_propagates_error_from_join_session(
        self,
        mock_join,
    ):
        invite = object()
        user = object()
        error = RuntimeError("join failed")

        mock_join.side_effect = error

        with self.assertRaises(RuntimeError) as context:
            accept_comparison_invite(
                invite,
                user,
            )

        self.assertIs(context.exception, error)
        mock_join.assert_called_once()

        call_args = mock_join.call_args
        self.assertEqual(
            call_args.args,
            (invite, user, ComparisonSession),
        )
        self.assertEqual(
            set(call_args.kwargs),
            {"notify"},
        )
