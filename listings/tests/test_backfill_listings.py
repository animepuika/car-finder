import os
from unittest.mock import call, patch

from django.core.management import call_command
from django.test import TestCase

from listings.models import TrackedSearch, CarListing

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')

BASE = 'https://www.ss.com/msg/lv/transport/cars/volkswagen'
# Rows in vw_list_page.html priced within the 1600 ceiling, or showing no price.
ELIGIBLE_URLS = {
    f'{BASE}/golf-4/ppmfm.html',   # 500
    f'{BASE}/sharan/bdcigo.html',  # 1,390
    f'{BASE}/golf-5/bcnlgg.html',  # no price shown
    f'{BASE}/t4/mfbjg.html',       # 1,600, exactly the ceiling
}


def _read_fixture(name):
    with open(os.path.join(FIXTURES_DIR, name), encoding='utf-8') as f:
        return f.read()


def _fetched_urls(mock_fetch_listing_page):
    return {c.args[0] for c in mock_fetch_listing_page.call_args_list}


class BackfillListingsCommandTests(TestCase):
    def setUp(self):
        self.tracked = TrackedSearch.objects.create(make='volkswagen', model='', max_price_eur=1600, active=True)
        self.list_page = _read_fixture('vw_list_page.html')
        self.detail_fixture = _read_fixture('golf3_listing_detail.html')
        self.cheap_detail = self.detail_fixture.replace(
            '<span class="ads_price" id="tdo_8">1 900 €</span>',
            '<span class="ads_price" id="tdo_8">900 €</span>',
        )

        sleep_patcher = patch('listings.management.commands.backfill_listings.time.sleep')
        sleep_patcher.start()
        self.addCleanup(sleep_patcher.stop)

    @patch('listings.ss_client.fetch_listing_page')
    @patch('listings.ss_client.fetch_for_sale_page')
    def test_only_fetches_and_saves_listings_within_the_price_ceiling(self, mock_fetch_for_sale_page, mock_fetch_listing_page):
        mock_fetch_for_sale_page.return_value = self.list_page
        mock_fetch_listing_page.return_value = self.cheap_detail

        call_command('backfill_listings')

        self.assertEqual(_fetched_urls(mock_fetch_listing_page), ELIGIBLE_URLS)
        self.assertEqual(set(CarListing.objects.values_list('listing_url', flat=True)), ELIGIBLE_URLS)
        listing = CarListing.objects.get(listing_url=f'{BASE}/golf-4/ppmfm.html')
        self.assertEqual(listing.model, 'golf-4')
        self.assertEqual(listing.price_eur, 900)

    @patch('listings.ss_client.fetch_listing_page')
    @patch('listings.ss_client.fetch_for_sale_page')
    def test_already_known_listings_are_not_refetched(self, mock_fetch_for_sale_page, mock_fetch_listing_page):
        known_url = f'{BASE}/golf-4/ppmfm.html'
        CarListing.objects.create(
            tracked_search=self.tracked, listing_url=known_url,
            make='volkswagen', model='golf-4', listing_type=CarListing.FOR_SALE,
        )
        mock_fetch_for_sale_page.return_value = self.list_page
        mock_fetch_listing_page.return_value = self.cheap_detail

        call_command('backfill_listings')

        self.assertEqual(CarListing.objects.count(), len(ELIGIBLE_URLS))
        self.assertEqual(_fetched_urls(mock_fetch_listing_page), ELIGIBLE_URLS - {known_url})

    @patch('listings.ss_client.fetch_listing_page')
    @patch('listings.ss_client.fetch_for_sale_page')
    def test_listing_whose_detail_page_price_is_over_the_ceiling_is_not_saved(self, mock_fetch_for_sale_page, mock_fetch_listing_page):
        mock_fetch_for_sale_page.return_value = self.list_page
        mock_fetch_listing_page.return_value = self.detail_fixture

        call_command('backfill_listings')

        self.assertEqual(CarListing.objects.count(), 0)

    @patch('listings.ss_client.fetch_listing_page')
    @patch('listings.ss_client.fetch_for_sale_page')
    def test_require_ta_excludes_listings_without_valid_ta(self, mock_fetch_for_sale_page, mock_fetch_listing_page):
        self.tracked.require_ta = True
        self.tracked.save()
        no_ta_detail = self.cheap_detail.replace(
            '<tr><td height="20" class="ads_opt_name" width="30" nowrap="">Tehniskā apskate:</td><td class="ads_opt" id="tdo_223" nowrap="">06.2027</td></tr>',
            '',
        )
        mock_fetch_for_sale_page.return_value = self.list_page
        mock_fetch_listing_page.return_value = no_ta_detail

        call_command('backfill_listings')

        self.assertEqual(CarListing.objects.count(), 0)

    @patch('listings.ss_client.fetch_listing_page')
    @patch('listings.ss_client.fetch_for_sale_page')
    def test_tracked_search_without_max_price_is_skipped(self, mock_fetch_for_sale_page, mock_fetch_listing_page):
        self.tracked.max_price_eur = None
        self.tracked.save()

        call_command('backfill_listings')

        mock_fetch_for_sale_page.assert_not_called()

    @patch('listings.ss_client.fetch_listing_page')
    @patch('listings.ss_client.fetch_for_sale_page')
    def test_scans_only_the_first_page_by_default(self, mock_fetch_for_sale_page, mock_fetch_listing_page):
        mock_fetch_for_sale_page.return_value = self.list_page
        mock_fetch_listing_page.return_value = self.cheap_detail

        call_command('backfill_listings')

        mock_fetch_for_sale_page.assert_called_once_with('volkswagen', 1)

    @patch('listings.ss_client.fetch_listing_page')
    @patch('listings.ss_client.fetch_for_sale_page')
    def test_scans_the_requested_number_of_pages(self, mock_fetch_for_sale_page, mock_fetch_listing_page):
        mock_fetch_for_sale_page.return_value = self.list_page
        mock_fetch_listing_page.return_value = self.cheap_detail

        call_command('backfill_listings', pages=2)

        self.assertEqual(mock_fetch_for_sale_page.call_args_list, [call('volkswagen', 1), call('volkswagen', 2)])

    @patch('listings.ss_client.fetch_listing_page')
    @patch('listings.ss_client.fetch_for_sale_page')
    def test_stops_paging_once_a_page_has_no_listings(self, mock_fetch_for_sale_page, mock_fetch_listing_page):
        mock_fetch_for_sale_page.side_effect = [self.list_page, '<html></html>', self.list_page]
        mock_fetch_listing_page.return_value = self.cheap_detail

        call_command('backfill_listings', pages=5)

        self.assertEqual(mock_fetch_for_sale_page.call_count, 2)
