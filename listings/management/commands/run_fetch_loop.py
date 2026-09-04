import sys
import time

from django.core.management import call_command
from django.core.management.base import BaseCommand

INTERVAL_SECONDS = 15 * 60


def run_one_cycle(stderr, style):
    try:
        call_command('fetch_listings')
    except Exception as exc:
        stderr.write(style.ERROR(f'fetch_listings failed: {exc}'))


class Command(BaseCommand):
    help = "Run fetch_listings on a loop, checking every 15 minutes, until stopped"

    def handle(self, *args, **options):
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

        while True:
            run_one_cycle(self.stderr, self.style)
            time.sleep(INTERVAL_SECONDS)
