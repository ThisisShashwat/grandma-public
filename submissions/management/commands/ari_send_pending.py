"""Send what is waiting in the Ari outbox (hand-ins and withdrawals that did not get through the first time). For a cron job, every few minutes:

    python manage.py ari_send_pending

One pass, no loops. Rows Ari refused (failed) are only tried again with --retry-failed. Does nothing while Ari is switched off (submissions/ari.py)."""
from django.core.management.base import BaseCommand

from pages.live import live
from submissions import ari


class Command(BaseCommand):
    help = "Send the pending Ari outbox rows once."

    def add_arguments(self, parser):
        parser.add_argument("--retry-failed", action="store_true", help="Also try the rows that failed (Ari said no, or there was no email) once more.")

    def handle(self, *args, **options):
        if not ari.enabled(live()):
            self.stdout.write("Ari is switched off or its environment values are missing: nothing sent.")
            return
        self.stdout.write(f"Tried {ari.send_pending(retry_failed=options['retry_failed'])} outbox rows.")
