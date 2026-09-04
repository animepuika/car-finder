from django.test import TestCase

from listings.models import CarListing, TrackedSearch
from listings.queries import cars_for_discord, listing_stats, tracked_search_summary


class CarsForDiscordTests(TestCase):
    def setUp(self):
        self.tracked = TrackedSearch.objects.create(make='volkswagen', model='golf-3')
        self._next_id = 0

    def _create(self, n, make='volkswagen', listing_type=CarListing.FOR_SALE):
        created = []
        for _ in range(n):
            self._next_id += 1
            created.append(CarListing.objects.create(
                tracked_search=self.tracked, listing_url=f'https://www.ss.com/msg/{self._next_id}.html',
                make=make, model='golf-3', listing_type=listing_type,
            ))
        return created

    def test_limits_results_and_reports_remaining_count(self):
        self._create(8)
        shown, remaining = cars_for_discord(limit=5)
        self.assertEqual(len(shown), 5)
        self.assertEqual(remaining, 3)

    def test_no_remaining_when_under_the_limit(self):
        self._create(3)
        shown, remaining = cars_for_discord(limit=5)
        self.assertEqual(len(shown), 3)
        self.assertEqual(remaining, 0)

    def test_make_filter_excludes_other_makes(self):
        self._create(2, make='volkswagen')
        self._create(2, make='skoda')
        shown, remaining = cars_for_discord(make='skoda', limit=5)
        self.assertEqual(len(shown), 2)
        self.assertTrue(all(c.make == 'skoda' for c in shown))

    def test_wanted_listings_are_excluded(self):
        self._create(2, listing_type=CarListing.FOR_SALE)
        self._create(3, listing_type=CarListing.WANTED)
        shown, remaining = cars_for_discord(limit=10)
        self.assertEqual(len(shown), 2)

    def test_cheapest_sort_orders_by_price_ascending(self):
        a, b, c = self._create(3)
        a.price_eur, b.price_eur, c.price_eur = 3000, 1000, 2000
        for listing in (a, b, c):
            listing.save()
        shown, _ = cars_for_discord(sort='cheapest', limit=10)
        self.assertEqual([c.price_eur for c in shown], [1000, 2000, 3000])


class ListingStatsTests(TestCase):
    def setUp(self):
        self.tracked = TrackedSearch.objects.create(make='volkswagen', model='golf-3')

    def _create(self, make, price_eur, listing_type=CarListing.FOR_SALE):
        return CarListing.objects.create(
            tracked_search=self.tracked, listing_url=f'https://www.ss.com/msg/{make}-{price_eur}.html',
            make=make, model='golf-3', price_eur=price_eur, listing_type=listing_type,
        )

    def test_totals_and_price_range_across_makes(self):
        self._create('volkswagen', 1000)
        self._create('volkswagen', 2000)
        self._create('skoda', 3000)
        self._create('audi', None)
        self._create('volkswagen', 500, listing_type=CarListing.WANTED)

        stats = listing_stats()

        self.assertEqual(stats['total'], 4)
        self.assertEqual(stats['min_price'], 1000)
        self.assertEqual(stats['max_price'], 3000)
        self.assertEqual(stats['avg_price'], 2000)
        by_make = {row['make']: row['count'] for row in stats['by_make']}
        self.assertEqual(by_make, {'volkswagen': 2, 'skoda': 1, 'audi': 1})


class TrackedSearchSummaryTests(TestCase):
    def test_only_active_searches_are_included(self):
        TrackedSearch.objects.create(make='volkswagen', model='', active=True)
        TrackedSearch.objects.create(make='skoda', model='', active=False)

        summary = tracked_search_summary()

        self.assertEqual([ts.make for ts in summary], ['volkswagen'])
