import datetime

from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from listings.models import TrackedSearch, CarListing


class TrackedSearchTests(TestCase):
    def test_make_model_pair_is_unique(self):
        TrackedSearch.objects.create(make='volkswagen', model='golf-3')
        with self.assertRaises(IntegrityError):
            TrackedSearch.objects.create(make='volkswagen', model='golf-3')

    def test_model_is_optional_for_brand_wide_tracking(self):
        tracked = TrackedSearch.objects.create(make='skoda', model='', max_price_eur=1200, require_ta=True)
        self.assertEqual(tracked.model, '')


class CarListingHasValidTaTests(TestCase):
    def setUp(self):
        self.tracked = TrackedSearch.objects.create(make='skoda', model='')

    def _listing(self, ta_valid_until):
        return CarListing.objects.create(
            tracked_search=self.tracked, listing_url=f'https://www.ss.com/msg/{ta_valid_until}.html',
            make='skoda', model='fabia', ta_valid_until=ta_valid_until,
        )

    def test_future_ta_date_is_valid(self):
        future = (timezone.now().date() + datetime.timedelta(days=30))
        self.assertTrue(self._listing(future).has_valid_ta)

    def test_past_ta_date_is_not_valid(self):
        past = (timezone.now().date() - datetime.timedelta(days=30))
        self.assertFalse(self._listing(past).has_valid_ta)

    def test_missing_ta_date_is_not_valid(self):
        self.assertFalse(self._listing(None).has_valid_ta)
