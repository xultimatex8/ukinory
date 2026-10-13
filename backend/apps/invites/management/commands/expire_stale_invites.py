from django.core.management.base import BaseCommand

from apps.invites.services.invite import expire_stale_invites


class Command(BaseCommand):
    help = "Mark overdue pending invites as expired."

    def handle(self, *args, **options):
        count = expire_stale_invites()
        self.stdout.write(f"Expired {count} invite(s).")
