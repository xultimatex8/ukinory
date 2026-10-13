from django.core.management.base import BaseCommand

from apps.swipe_sessions.services.session import close_stale_swipe_sessions


class Command(BaseCommand):
    help = "Close abandoned swipe sessions."

    def handle(self, *args, **options):
        closed = close_stale_swipe_sessions()
        self.stdout.write(f"Closed {closed} abandoned swipe session(s).")
