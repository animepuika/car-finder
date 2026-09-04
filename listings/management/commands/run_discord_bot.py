import os
import sys

from django.core.management.base import BaseCommand

from listings.discord_bot import build_client


class Command(BaseCommand):
    help = "Run the Discord bot that answers /cars queries"

    def handle(self, *args, **options):
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

        token = os.environ.get('DISCORD_BOT_TOKEN')
        if not token:
            self.stderr.write(self.style.ERROR('DISCORD_BOT_TOKEN is not set in .env'))
            return

        client = build_client()
        client.run(token)
