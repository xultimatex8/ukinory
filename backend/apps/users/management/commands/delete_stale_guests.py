from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from django.utils import timezone

from apps.swipe_sessions.models import SwipeSession
from apps.swipe_sessions.services.cleanup import delete_orphaned_sessions

GUEST_STALE_AFTER = timedelta(hours=12)

User = get_user_model()


class Command(BaseCommand):
    help = "Deletes guest accounts with no recent activity."

    def handle(self, *args, **options):
        cutoff = timezone.now() - GUEST_STALE_AFTER

        stale_guests = (
            User.objects.filter(is_guest=True)
            .filter(
                Q(last_active_at__lt=cutoff)
                | Q(last_active_at__isnull=True, created_at__lt=cutoff)
            )
            .annotate(
                swipes_count=Count("swipes", distinct=True),
                ratings_count=Count("ratings", distinct=True),
                watchlist_count=Count("watchlist_entries", distinct=True),
                sessions_count=Count("swipe_sessions", distinct=True),
            )
        )

        stale_guest_list = list(stale_guests)
        if not stale_guest_list:
            self.stdout.write("No inactive guests found.")
            return

        self.stdout.write(f"Found {len(stale_guest_list)} inactive guests:")
        for user in stale_guest_list:
            self.stdout.write(
                f"  - {user.username} (id={user.pk}, last_active_at={user.last_active_at}) "
                f"swipes={user.swipes_count} ratings={user.ratings_count} "
                f"watchlist={user.watchlist_count} sessions={user.sessions_count}"
            )

        pks = [user.pk for user in stale_guest_list]

        affected_session_ids = list(
            SwipeSession.objects.filter(users__in=pks).values_list("pk", flat=True).distinct()
        )

        total_deleted, deleted_per_model = User.objects.filter(pk__in=pks).delete()

        self.stdout.write(
            self.style.SUCCESS(f"Deleted {len(stale_guest_list)} inactive guests.")
        )
        self.stdout.write(f"Total rows deleted (including cascade): {total_deleted}")
        for model_label, count in sorted(deleted_per_model.items()):
            if count:
                self.stdout.write(f"  - {model_label}: {count}")

        _, orphaned_per_model = delete_orphaned_sessions(session_ids=affected_session_ids)
        orphaned_sessions = orphaned_per_model.get("swipe_sessions.SwipeSession", 0)
        if orphaned_sessions:
            self.stdout.write(f"Deleted {orphaned_sessions} orphaned swipe sessions.")
