import datetime

from django.utils import timezone

from .models import CarListing

PERIOD_DAYS = {'today': 1, 'week': 7, 'month': 30}


def for_sale_listings(make=None, period=None):
    listings = CarListing.objects.filter(listing_type=CarListing.FOR_SALE)
    if make:
        listings = listings.filter(make=make)
    if period in PERIOD_DAYS:
        cutoff = timezone.now() - datetime.timedelta(days=PERIOD_DAYS[period])
        listings = listings.filter(first_seen_at__gte=cutoff)
    return listings


def cars_for_discord(make=None, period=None, limit=5):
    """Returns (shown, remaining_count) for a /cars query - shown is at
    most `limit` CarListing objects, remaining_count is how many more
    matched beyond that."""
    qs = for_sale_listings(make=make, period=period).order_by('-first_seen_at')
    total = qs.count()
    shown = list(qs[:limit])
    remaining = max(0, total - len(shown))
    return shown, remaining
