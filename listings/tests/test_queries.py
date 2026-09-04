from django.test import TestCase

from listings.models import CarListing, TrackedSearch
from listings.queries import cars_for_discord


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
