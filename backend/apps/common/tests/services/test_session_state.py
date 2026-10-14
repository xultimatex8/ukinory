from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.common.enums import SessionStatus, SessionType
from apps.common.models import Session
from apps.common.services.session_state import build_participant_state
from apps.library.models import Rating
from apps.movies.models import Movie

User = get_user_model()


class BuildParticipantStateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="a@x.com", username="a", password="pw"
        )
        self.partner = User.objects.create_user(
            email="b@x.com", username="b", password="pw"
        )
        self.session = Session.objects.create(
            session_type=SessionType.COMPARISON_SESSION,
        )
        self.session.users.add(self.user)

    def _rate(self, user, tmdb_id, title, year):
        movie = Movie.objects.create(
            tmdb_id=tmdb_id, title=title, release_year=year
        )
        Rating.objects.create(
            user=user,
            title=title,
            release_year=year,
            movie=movie,
            rating=5,
        )

    def test_alone_in_session(self):
        state = build_participant_state(self.session, self.user)

        self.assertEqual(
            state,
            {
                "id": str(self.session.pk),
                "status": SessionStatus.WAITING,
                "participants": 1,
                "partner_joined": False,
                "you_have_data": False,
                "partner_has_data": None,
            },
        )

    def test_partner_joined_without_data(self):
        self.session.users.add(self.partner)

        state = build_participant_state(self.session, self.user)

        self.assertEqual(state["participants"], 2)
        self.assertTrue(state["partner_joined"])
        self.assertFalse(state["you_have_data"])
        self.assertFalse(state["partner_has_data"])

    def test_only_current_user_has_data(self):
        self.session.users.add(self.partner)
        self._rate(self.user, 1, "Dune", 2021)

        state = build_participant_state(self.session, self.user)

        self.assertTrue(state["you_have_data"])
        self.assertFalse(state["partner_has_data"])

    def test_state_is_relative_to_the_requesting_user(self):
        self.session.users.add(self.partner)
        self._rate(self.partner, 2, "Interstellar", 2014)

        mine = build_participant_state(self.session, self.user)
        theirs = build_participant_state(self.session, self.partner)

        self.assertFalse(mine["you_have_data"])
        self.assertTrue(mine["partner_has_data"])
        self.assertTrue(theirs["you_have_data"])
        self.assertFalse(theirs["partner_has_data"])
