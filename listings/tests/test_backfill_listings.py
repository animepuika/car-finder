import os
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from listings.models import TrackedSearch, CarListing

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')


def _read_fixture(name):
    with open(os.path.join(FIXTURES_DIR, name), encoding='utf-8') as f:
        return f.read()


class BackfillListingsCommandTests(TestCase):
    def setUp(self):
        self.tracked = TrackedSearch.objects.create(make='volkswagen', model='', max_price_eur=1200, active=True)
        self.filter_results = _read_fixture('skoda_filter_results.html')
        self.detail_fixture = _read_fixture('golf3_listing_detail.html')

    @patch('listings.ss_client.fetch_listing_page')
    @patch('listings.ss_client.fetch_filtered_page')
    def test_creates_listings_from_filtered_results(self, mock_fetch_filtered_page, mock_fetch_listing_page):
        mock_fetch_filtered_page.return_value = self.filter_results
        mock_fetch_listing_page.return_value = self.detail_fixture

        call_command('backfill_listings')

        self.assertEqual(CarListing.objects.count(), 2)
        listing = CarListing.objects.get(listing_url__endswith='ckjje.html')
        self.assertEqual(listing.model, 'golf-3')
        self.assertEqual(listing.price_eur, 1900)

    @patch('listings.ss_client.fetch_listing_page')
    @patch('listings.ss_client.fetch_filtered_page')
    def test_already_known_listings_are_not_refetched(self, mock_fetch_filtered_page, mock_fetch_listing_page):
        CarListing.objects.create(
            tracked_search=self.tracked,
            listing_url='https://www.ss.com/msg/lv/transport/cars/volkswagen/golf-3/ckjje.html',
            make='volkswagen', model='golf-3', listing_type=CarListing.FOR_SALE,
        )
        mock_fetch_filtered_page.return_value = self.filter_results
        mock_fetch_listing_page.return_value = self.detail_fixture

        call_command('backfill_listings')

        self.assertEqual(CarListing.objects.count(), 2)
        mock_fetch_listing_page.assert_called_once()

    @patch('listings.ss_client.fetch_listing_page')
    @patch('listings.ss_client.fetch_filtered_page')
    def test_require_ta_excludes_listings_without_valid_ta(self, mock_fetch_filtered_page, mock_fetch_listing_page):
        self.tracked.require_ta = True
        self.tracked.save()
        no_ta_detail = self.detail_fixture.replace(
            '<tr><td height="20" class="ads_opt_name" width="30" nowrap="">Tehniskā apskate:</td><td class="ads_opt" id="tdo_223" nowrap="">06.2027</td></tr>',
            '',
        )
        mock_fetch_filtered_page.return_value = self.filter_results
        mock_fetch_listing_page.return_value = no_ta_detail

        call_command('backfill_listings')

        self.assertEqual(CarListing.objects.count(), 0)

    @patch('listings.ss_client.fetch_listing_page')
    @patch('listings.ss_client.fetch_filtered_page')
    def test_tracked_search_without_max_price_is_skipped(self, mock_fetch_filtered_page, mock_fetch_listing_page):
        self.tracked.max_price_eur = None
        self.tracked.save()

        call_command('backfill_listings')

        mock_fetch_filtered_page.assert_not_called()
