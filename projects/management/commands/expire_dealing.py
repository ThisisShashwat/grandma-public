"""Abandon every `dealing` project nobody came back to for DEALING_EXPIRY_DAYS (an admin setting). For a daily cron job:

    python manage.py expire_dealing

The same thing happens for one person when they open Talk to Grandma (projects/expiry.py), so this only tidies up people who never return."""
from django.core.management.base import BaseCommand

from projects import expiry


class Command(BaseCommand):
    help = "Abandon the dealing projects nobody came back to (DEALING_EXPIRY_DAYS days)."

    def handle(self, *args, **options):
        self.stdout.write(f"Expired {expiry.expire_stale()} dealing projects.")
