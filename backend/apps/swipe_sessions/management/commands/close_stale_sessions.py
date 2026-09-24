from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from apps.common.enums import SwipeSessionStatus
from apps.swipe_sessions.models import SwipeSession
from apps.swipe_sessions.services.session import STALE_SESSION_TIMEOUT, ensure_session_finished

STALE_AFTER = STALE_SESSION_TIMEOUT


class Command(BaseCommand):
    help = "Closes abandoned swipe sessions (no recnt activity)."

    def handle(self, *args, **options):
        cutoff = timezone.now() - STALE_AFTER

        stale_sessions = SwipeSession.objects.filter(
            status__in=[SwipeSessionStatus.WAITING, SwipeSessionStatus.ACTIVE],
        ).filter(
            Q(last_seen_at__lt=cutoff) | Q(last_seen_at__isnull=True, created_at__lt=cutoff)
        )

        closed = 0
        for session in stale_sessions:
            if ensure_session_finished(session.pk) is not None:
                closed += 1

        self.stdout.write(self.style.SUCCESS(f"Closed {closed} inactive sessions."))
