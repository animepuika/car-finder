import sys
import time

from django.core.management.base import BaseCommand
from django.utils import timezone

from listings import ss_client, ss_parser
from listings.models import CarListing, TrackedSearch

REQUEST_DELAY_SECONDS = 1


class Command(BaseCommand):
    help = "Pull in already-existing ss.com listings for tracked searches with a price ceiling set"

    def add_arguments(self, parser):
        parser.add_argument(
            '--pages', type=int, default=1,
            help='How many pages (30 newest for-sale ads each) to scan per tracked search',
        )

    def handle(self, *args, **options):
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')

        for tracked_search in TrackedSearch.objects.filter(active=True):
            if tracked_search.max_price_eur is None:
                self.stdout.write(f'{tracked_search}: skipped, no max_price_eur set')
                continue
            try:
                new_count = self._backfill_for_search(tracked_search, options['pages'])
                self.stdout.write(self.style.SUCCESS(f'{tracked_search}: {new_count} new from backfill'))
            except Exception as exc:
                self.stderr.write(self.style.ERROR(f'Backfill failed for {tracked_search}: {exc}'))

    def _backfill_for_search(self, tracked_search, pages):
        new_count = 0
        for page in range(1, pages + 1):
            rows = ss_parser.parse_listing_rows(ss_client.fetch_for_sale_page(tracked_search.make, page))
            if not rows:
                break
            for row in rows:
                if self._save_listing(tracked_search, row):
                    new_count += 1
            time.sleep(REQUEST_DELAY_SECONDS)
        return new_count

    def _save_listing(self, tracked_search, row):
        url = row['listing_url']
        if row['price_eur'] is not None and row['price_eur'] > tracked_search.max_price_eur:
            return False
        if CarListing.objects.filter(listing_url=url).exists():
            return False

        try:
            detail_html = ss_client.fetch_listing_page(url)
            details = ss_parser.parse_listing_detail(detail_html)
        except Exception as exc:
            self.stderr.write(self.style.WARNING(f'Detail fetch failed for {url}: {exc}'))
            return False
        finally:
            time.sleep(REQUEST_DELAY_SECONDS)

        if details['listing_type'] != CarListing.FOR_SALE:
            return False

        if details['price_eur'] is not None and details['price_eur'] > tracked_search.max_price_eur:
            return False

        if tracked_search.require_ta:
            if details['ta_valid_until'] is None or details['ta_valid_until'] < timezone.now().date():
                return False

        CarListing.objects.create(
            tracked_search=tracked_search,
            listing_url=url,
            make=tracked_search.make,
            model=ss_parser.parse_model_from_listing_url(url) or tracked_search.model,
            year=details['year'],
            engine=details['engine'],
            transmission=details['transmission'],
            body_type=details['body_type'],
            color=details['color'],
            mileage_km=details['mileage_km'],
            price_eur=details['price_eur'],
            listing_type=details['listing_type'],
            ta_valid_until=details['ta_valid_until'],
            thumbnail_url=(details['photo_urls'][0] if details['photo_urls'] else ''),
            photo_urls=details['photo_urls'],
            description=details['description'],
        )
        return True
