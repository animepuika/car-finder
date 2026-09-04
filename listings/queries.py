import datetime

from django.db.models import Avg, Count, Max, Min
from django.utils import timezone

from .models import CarListing, TrackedSearch

PERIOD_DAYS = {'today': 1, 'week': 7, 'month': 30}

SORT_OPTIONS = {
    'newest': '-first_seen_at',
    'cheapest': 'price_eur',
    'lowest_mileage': 'mileage_km',
}


def for_sale_listings(make=None, period=None):
    listings = CarListing.objects.filter(listing_type=CarListing.FOR_SALE)
    if make:
        listings = listings.filter(make=make)
    if period in PERIOD_DAYS:
        cutoff = timezone.now() - datetime.timedelta(days=PERIOD_DAYS[period])
        listings = listings.filter(first_seen_at__gte=cutoff)
    return listings


def cars_for_discord(make=None, period=None, sort='newest', limit=5):
    """Returns (shown, remaining_count) for a /cars query - shown is at
    most `limit` CarListing objects, remaining_count is how many more
    matched beyond that."""
    order = SORT_OPTIONS.get(sort, SORT_OPTIONS['newest'])
    qs = for_sale_listings(make=make, period=period).order_by(order)
    total = qs.count()
    shown = list(qs[:limit])
    remaining = max(0, total - len(shown))
    return shown, remaining


def listing_stats():
    """Aggregate counts/prices for a /stats overview: total for-sale
    count, per-make breakdown, and price range across all of them."""
    qs = CarListing.objects.filter(listing_type=CarListing.FOR_SALE)
    by_make = list(
        qs.values('make').annotate(count=Count('id')).order_by('-count')
    )
    price_stats = qs.exclude(price_eur__isnull=True).aggregate(
        min_price=Min('price_eur'), max_price=Max('price_eur'), avg_price=Avg('price_eur'),
    )
    return {
        'total': qs.count(),
        'by_make': by_make,
        'min_price': price_stats['min_price'],
        'max_price': price_stats['max_price'],
        'avg_price': round(price_stats['avg_price']) if price_stats['avg_price'] else None,
    }


def tracked_search_summary():
    """Active TrackedSearch rows for a /tracked overview."""
    return list(TrackedSearch.objects.filter(active=True).order_by('make'))
