from django.core.management.base import BaseCommand

from apps.comparisons.services.room import close_stale_rooms
from apps.invites.services.invite import expire_stale_invites


class Command(BaseCommand):
    help = "Mark overdue pending invites as expired and drop abandoned comparison rooms."

    def handle(self, *args, **options):
        count = expire_stale_invites()
        self.stdout.write(f"Expired {count} invite(s).")

        rooms = close_stale_rooms()
        self.stdout.write(f"Removed {rooms} abandoned comparison room(s).")
