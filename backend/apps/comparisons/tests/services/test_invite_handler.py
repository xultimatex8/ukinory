from __future__ import annotations

from unittest import mock

from django.test import TestCase

from apps.comparisons.services.invite_handler import (
    accept_comparison_invite,
)


class AcceptComparisonInviteTests(TestCase):
    @mock.patch(
        "apps.comparisons.services.invite_handler.join_room_from_invite"
    )
    def test_accepts_invite_and_returns_session(
        self,
        mock_join,
    ):
        invite = object()
        user = object()
        expected_room = object()

        mock_join.return_value = expected_room

        result = accept_comparison_invite(
            invite,
            user,
        )

        self.assertIs(result, expected_room)
        mock_join.assert_called_once_with(
            invite,
            user,
        )

    @mock.patch(
        "apps.comparisons.services.invite_handler.join_room_from_invite"
    )
    def test_propagates_error_from_join_room(
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
