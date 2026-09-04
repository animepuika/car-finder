import os
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from listings.models import TrackedSearch, CarListing

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')


def _read_fixture(name):
    with open(os.path.join(FIXTURES_DIR, name), encoding='utf-8') as f:
        return f.read()


class FetchListingsCommandTests(TestCase):
    def setUp(self):
        self.tracked = TrackedSearch.objects.create(make='volkswagen', model='golf-3', active=True)
        self.rss_fixture = _read_fixture('golf3_rss.xml')
        self.detail_fixture = _read_fixture('golf3_listing_detail.html')

    @patch('listings.ss_client.fetch_listing_page')
    @patch('listings.ss_client.fetch_rss')
    def test_creates_listings_split_by_type(self, mock_fetch_rss, mock_fetch_listing_page):
        mock_fetch_rss.return_value = self.rss_fixture
        mock_fetch_listing_page.return_value = self.detail_fixture

        call_command('fetch_listings')

        self.assertEqual(CarListing.objects.filter(listing_type='for_sale').count(), 2)
        self.assertEqual(CarListing.objects.filter(listing_type='wanted').count(), 1)

    @patch('listings.ss_client.fetch_listing_page')
    @patch('listings.ss_client.fetch_rss')
    def test_second_run_does_not_duplicate(self, mock_fetch_rss, mock_fetch_listing_page):
        mock_fetch_rss.return_value = self.rss_fixture
        mock_fetch_listing_page.return_value = self.detail_fixture

        call_command('fetch_listings')
        call_command('fetch_listings')

        self.assertEqual(CarListing.objects.count(), 3)

    @patch('listings.ss_client.fetch_listing_page')
    @patch('listings.ss_client.fetch_rss')
    def test_detail_fetch_failure_still_saves_rss_data(self, mock_fetch_rss, mock_fetch_listing_page):
        mock_fetch_rss.return_value = self.rss_fixture
        mock_fetch_listing_page.side_effect = Exception('network error')

        call_command('fetch_listings')

        listing = CarListing.objects.get(listing_url__endswith='ckjje.html')
        self.assertEqual(listing.year, 1997)
        self.assertEqual(listing.price_eur, 1500)

    @patch('listings.ss_client.fetch_listing_page')
    @patch('listings.ss_client.fetch_rss')
    def test_one_failing_tracked_search_does_not_block_others(self, mock_fetch_rss, mock_fetch_listing_page):
        TrackedSearch.objects.create(make='bmw', model='e30', active=True)

        def fetch_rss_side_effect(make, model=None):
            if make == 'bmw':
                raise Exception('site unreachable')
            return self.rss_fixture

        mock_fetch_rss.side_effect = fetch_rss_side_effect
        mock_fetch_listing_page.return_value = self.detail_fixture

        call_command('fetch_listings')

        self.assertEqual(CarListing.objects.filter(tracked_search=self.tracked).count(), 3)

    @patch('listings.ss_client.fetch_listing_page')
    @patch('listings.ss_client.fetch_rss')
    def test_brand_wide_search_uses_rss_model_field(self, mock_fetch_rss, mock_fetch_listing_page):
        TrackedSearch.objects.create(make='volkswagen', model='', active=True)
        mock_fetch_rss.return_value = _read_fixture('vw_brand_rss.xml')
        mock_fetch_listing_page.return_value = self.detail_fixture

        call_command('fetch_listings')

        touran = CarListing.objects.get(listing_url__endswith='cefgfx.html')
        self.assertEqual(touran.model, 'Touran')

    @patch('listings.ss_client.fetch_listing_page')
    @patch('listings.ss_client.fetch_rss')
    def test_price_over_ceiling_is_skipped_without_a_detail_fetch(self, mock_fetch_rss, mock_fetch_listing_page):
        self.tracked.max_price_eur = 1000
        self.tracked.save()
        single_expensive_item_rss = '''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<item>
<title><![CDATA[ Automāts. 300eur Pirmā iemaksa. ]]></title>
<link>https://www.ss.com/msg/lv/transport/cars/volkswagen/golf-3/ckjje.html</link>
<pubDate>Wed, 02 Sep 2026 21:11:55 +0300</pubDate>
<description><![CDATA[ <a href="https://www.ss.com/msg/lv/transport/cars/volkswagen/golf-3/ckjje.html"><img align=right border=0 src="https://i.ss.com/gallery/8/1540/384904/76980748.t.jpg" width="174" height="130" alt=""></a> Gads: <b>1997</b><br/>Tilpums: <b>1.8</b><br/>Cena: <b>1,500 €</b><br/><br/> ]]></description>
</item>
</channel></rss>'''
        mock_fetch_rss.return_value = single_expensive_item_rss

        call_command('fetch_listings')

        self.assertFalse(CarListing.objects.filter(listing_url__endswith='ckjje.html').exists())
        mock_fetch_listing_page.assert_not_called()

    @patch('listings.ss_client.fetch_listing_page')
    @patch('listings.ss_client.fetch_rss')
    def test_require_ta_excludes_listings_without_valid_ta(self, mock_fetch_rss, mock_fetch_listing_page):
        self.tracked.require_ta = True
        self.tracked.save()
        no_ta_detail = self.detail_fixture.replace(
            '<tr><td height="20" class="ads_opt_name" width="30" nowrap="">Tehniskā apskate:</td><td class="ads_opt" id="tdo_223" nowrap="">06.2027</td></tr>',
            '',
        )
        mock_fetch_rss.return_value = self.rss_fixture
        mock_fetch_listing_page.return_value = no_ta_detail

        call_command('fetch_listings')

        self.assertEqual(CarListing.objects.filter(listing_type='for_sale').count(), 0)
