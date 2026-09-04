from django.test import TestCase
from django.urls import reverse

from listings.models import TrackedSearch, CarListing


class CarListViewTests(TestCase):
    def setUp(self):
        self.tracked = TrackedSearch.objects.create(make='volkswagen', model='golf-3')
        CarListing.objects.create(
            tracked_search=self.tracked, listing_url='https://www.ss.com/msg/a.html',
            make='volkswagen', model='golf-3', year=2000, price_eur=1900,
            listing_type=CarListing.FOR_SALE,
        )
        CarListing.objects.create(
            tracked_search=self.tracked, listing_url='https://www.ss.com/msg/b.html',
            make='volkswagen', model='golf-3', listing_type=CarListing.WANTED,
        )

    def test_only_for_sale_listings_are_shown(self):
        response = self.client.get(reverse('car_list'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['listings']), 1)

    def test_price_filter(self):
        response = self.client.get(reverse('car_list'), {'price_max': '1000'})
        self.assertEqual(len(response.context['listings']), 0)
