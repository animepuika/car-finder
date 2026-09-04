import datetime
import os

from django.test import SimpleTestCase

from listings import ss_parser

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')


def _read_fixture(name):
    with open(os.path.join(FIXTURES_DIR, name), encoding='utf-8') as f:
        return f.read()


class ParseRssFeedTests(SimpleTestCase):
    def setUp(self):
        self.xml_text = _read_fixture('golf3_rss.xml')

    def test_parses_three_items(self):
        items = ss_parser.parse_rss_feed(self.xml_text)
        self.assertEqual(len(items), 3)

    def test_for_sale_listing_without_mileage(self):
        items = ss_parser.parse_rss_feed(self.xml_text)
        item = next(i for i in items if i['listing_url'].endswith('ckjje.html'))
        self.assertEqual(item['year'], 1997)
        self.assertEqual(item['engine'], '1.8')
        self.assertIsNone(item['mileage_km'])
        self.assertEqual(item['price_eur'], 1500)
        self.assertEqual(item['listing_type'], 'for_sale')
        self.assertTrue(item['thumbnail_url'].endswith('76980748.t.jpg'))

    def test_for_sale_listing_with_mileage_in_thousands(self):
        items = ss_parser.parse_rss_feed(self.xml_text)
        item = next(i for i in items if i['listing_url'].endswith('cfojc.html'))
        self.assertEqual(item['mileage_km'], 252000)
        self.assertEqual(item['price_eur'], 950)

    def test_wanted_listing_has_no_price_or_specs(self):
        items = ss_parser.parse_rss_feed(self.xml_text)
        item = next(i for i in items if i['listing_url'].endswith('deofm.html'))
        self.assertEqual(item['listing_type'], 'wanted')
        self.assertIsNone(item['price_eur'])
        self.assertIsNone(item['year'])

    def test_model_specific_feed_has_no_model_field(self):
        items = ss_parser.parse_rss_feed(self.xml_text)
        self.assertTrue(all(item['model'] is None for item in items))


class ParseBrandRssFeedTests(SimpleTestCase):
    def test_brand_wide_feed_includes_model_per_item(self):
        xml_text = _read_fixture('vw_brand_rss.xml')
        items = ss_parser.parse_rss_feed(xml_text)
        by_url = {i['listing_url']: i for i in items}
        touran = by_url['https://www.ss.com/msg/lv/transport/cars/volkswagen/touran/cefgfx.html']
        touareg = by_url['https://www.ss.com/msg/lv/transport/cars/volkswagen/touareg/alefo.html']
        self.assertEqual(touran['model'], 'Touran')
        self.assertEqual(touran['price_eur'], 1650)
        self.assertEqual(touareg['model'], 'Touareg')
        self.assertEqual(touareg['price_eur'], 56850)


class ParseListingDetailTests(SimpleTestCase):
    def test_parses_full_specs(self):
        html_text = _read_fixture('golf3_listing_detail.html')
        details = ss_parser.parse_listing_detail(html_text)
        self.assertEqual(details['year'], 2000)
        self.assertEqual(details['engine'], '1.9 dīzelis')
        self.assertEqual(details['transmission'], 'Manuāla 5 ātrumi')
        self.assertEqual(details['mileage_km'], 264231)
        self.assertEqual(details['color'], 'Zila')
        self.assertEqual(details['body_type'], 'Kabriolets')
        self.assertEqual(details['price_eur'], 1900)
        self.assertEqual(len(details['photo_urls']), 4)
        self.assertIn('Pārdodu VW Golf Cabriolet', details['description'])

    def test_parses_ta_valid_until_as_last_day_of_month(self):
        html_text = _read_fixture('golf3_listing_detail.html')
        details = ss_parser.parse_listing_detail(html_text)
        self.assertEqual(details['ta_valid_until'], datetime.date(2027, 6, 30))

    def test_missing_ta_row_gives_none(self):
        html_text = _read_fixture('golf3_listing_detail.html').replace(
            '<tr><td height="20" class="ads_opt_name" width="30" nowrap="">Tehniskā apskate:</td><td class="ads_opt" id="tdo_223" nowrap="">06.2027</td></tr>',
            '',
        )
        details = ss_parser.parse_listing_detail(html_text)
        self.assertIsNone(details['ta_valid_until'])

    def test_detail_page_reports_wanted_listing_type(self):
        html_text = _read_fixture('golf3_listing_detail.html').replace(
            '<span class="ads_price" id="tdo_8">1 900 €</span>', '<span class="ads_price" id="tdo_8">pērku</span>',
        )
        details = ss_parser.parse_listing_detail(html_text)
        self.assertEqual(details['listing_type'], 'wanted')
        self.assertIsNone(details['price_eur'])


class ParseListingUrlsTests(SimpleTestCase):
    def test_extracts_unique_listing_urls_from_a_results_page(self):
        html_text = '''
        <html><body>
        <a href="/msg/lv/transport/cars/skoda/fabia/aaa.html">Fabia</a>
        <a href="/msg/lv/transport/cars/skoda/octavia/bbb.html">Octavia</a>
        <a href="/msg/lv/transport/cars/skoda/fabia/aaa.html">Fabia (photo link, same ad)</a>
        <a href="/lv/transport/cars/skoda/fDgSeF4belM=.html">honeypot, must be ignored</a>
        </body></html>
        '''
        urls = ss_parser.parse_listing_urls(html_text)
        self.assertEqual(urls, [
            'https://www.ss.com/msg/lv/transport/cars/skoda/fabia/aaa.html',
            'https://www.ss.com/msg/lv/transport/cars/skoda/octavia/bbb.html',
        ])


class ParseModelFromListingUrlTests(SimpleTestCase):
    def test_extracts_model_slug(self):
        url = 'https://www.ss.com/msg/lv/transport/cars/skoda/fabia/aaa.html'
        self.assertEqual(ss_parser.parse_model_from_listing_url(url), 'fabia')

    def test_returns_none_for_an_unrecognised_url(self):
        self.assertIsNone(ss_parser.parse_model_from_listing_url('https://www.ss.com/lv/transport/cars/skoda/'))
