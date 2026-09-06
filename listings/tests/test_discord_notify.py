import os
from unittest.mock import patch

import requests
from django.test import TestCase

from listings import discord_notify
from listings.models import CarListing, TrackedSearch


class NotifyNewListingTests(TestCase):
    def setUp(self):
        tracked = TrackedSearch.objects.create(make='volkswagen', model='golf-3')
        self.listing = CarListing.objects.create(
            tracked_search=tracked, listing_url='https://www.ss.com/msg/a.html',
            make='volkswagen', model='golf-3', year=2000, price_eur=1900,
            listing_type=CarListing.FOR_SALE,
            photo_urls=['https://i.ss.com/gallery/1/a.jpg'],
        )
        self.warnings = []

    def _warn(self, message):
        self.warnings.append(message)

    @patch.dict(os.environ, {'DISCORD_WEBHOOK_URL': 'https://discord.com/api/webhooks/test/test'})
    @patch('listings.discord_notify.requests.post')
    def test_posts_make_model_price_link_and_photo(self, mock_post):
        mock_post.return_value.raise_for_status.return_value = None

        discord_notify.notify_new_listing(self.listing, self._warn)

        mock_post.assert_called_once()
        url, kwargs = mock_post.call_args[0][0], mock_post.call_args[1]
        self.assertEqual(url, 'https://discord.com/api/webhooks/test/test')
        content = kwargs['json']['content']
        self.assertIn('NEW IN', content)
        self.assertIn('volkswagen golf-3', content)

        embed = kwargs['json']['embeds'][0]
        self.assertIn('volkswagen golf-3', embed['title'])
        self.assertIn('2000', embed['title'])
        self.assertEqual(embed['url'], 'https://www.ss.com/msg/a.html')
        self.assertIn('1900', embed['description'])
        self.assertEqual(embed['thumbnail']['url'], 'https://i.ss.com/gallery/1/a.jpg')
        self.assertEqual(self.warnings, [])

    @patch.dict(os.environ, {}, clear=True)
    @patch('listings.discord_notify.requests.post')
    def test_does_nothing_when_no_webhook_configured(self, mock_post):
        discord_notify.notify_new_listing(self.listing, self._warn)

        mock_post.assert_not_called()
        self.assertEqual(self.warnings, [])

    @patch.dict(os.environ, {'DISCORD_WEBHOOK_URL': 'https://discord.com/api/webhooks/test/test'})
    @patch('listings.discord_notify.requests.post')
    def test_network_failure_warns_but_does_not_raise(self, mock_post):
        mock_post.side_effect = requests.RequestException('network error')

        discord_notify.notify_new_listing(self.listing, self._warn)

        self.assertEqual(len(self.warnings), 1)
        self.assertIn('network error', self.warnings[0])
