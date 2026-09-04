import sys

from django.core.management.base import BaseCommand

from listings import ss_client, ss_parser
from listings.listing_sync import save_new_listing
from listings.models import TrackedSearch


class Command(BaseCommand):
    help = "Fetch new car listings from ss.com for all active tracked searches"

    def handle(self, *args, **options):
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')

        for tracked_search in TrackedSearch.objects.filter(active=True):
            try:
                self._fetch_for_search(tracked_search)
            except Exception as exc:
                self.stderr.write(self.style.ERROR(f'Failed to fetch {tracked_search}: {exc}'))

    def _fetch_for_search(self, tracked_search):
        xml_text = ss_client.fetch_rss(tracked_search.make, tracked_search.model or None)
        items = ss_parser.parse_rss_feed(xml_text)

        new_count = 0
        for item in items:
            created = save_new_listing(
                tracked_search, item,
                warn=lambda msg: self.stderr.write(self.style.WARNING(msg)),
            )
            if created:
                new_count += 1

        self.stdout.write(self.style.SUCCESS(f'{tracked_search}: {len(items)} seen, {new_count} new'))
