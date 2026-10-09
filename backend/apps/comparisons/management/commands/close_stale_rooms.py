from django.core.management.base import BaseCommand

from apps.comparisons.services.room import close_stale_rooms


class Command(BaseCommand):
    help = "Drop abandoned comparison rooms."

    def handle(self, *args, **options):
        rooms = close_stale_rooms()
        self.stdout.write(f"Removed {rooms} abandoned comparison room(s).")
