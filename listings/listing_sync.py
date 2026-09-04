import time

from listings import ss_client, ss_parser
from listings.models import CarListing

REQUEST_DELAY_SECONDS = 1


def save_new_listing(tracked_search, item, warn):
    """Create a CarListing for a new RSS/backfill item, or update
    last_seen_at/price if it's already known. Returns True if a new row
    was created, False otherwise (already existed, or excluded by the
    tracked search's price ceiling or TA requirement).

    `warn(message)` is called for non-fatal problems (e.g. a detail-page
    fetch failing) - the caller decides how to surface it (stdout style,
    logging, etc.) so this module has no Command dependency."""
    is_for_sale = item['listing_type'] == CarListing.FOR_SALE

    if is_for_sale and tracked_search.max_price_eur is not None:
        if item['price_eur'] is not None and item['price_eur'] > tracked_search.max_price_eur:
            return False

    existing = CarListing.objects.filter(listing_url=item['listing_url']).first()
    if existing:
        if item['price_eur'] is not None:
            existing.price_eur = item['price_eur']
        existing.save()
        return False

    details = {}
    if is_for_sale:
        try:
            detail_html = ss_client.fetch_listing_page(item['listing_url'])
            details = ss_parser.parse_listing_detail(detail_html)
        except Exception as exc:
            warn(f'Detail fetch failed for {item["listing_url"]}: {exc}')
        time.sleep(REQUEST_DELAY_SECONDS)

        if tracked_search.require_ta:
            ta_valid_until = details.get('ta_valid_until')
            if ta_valid_until is None or ta_valid_until < _today():
                return False

    CarListing.objects.create(
        tracked_search=tracked_search,
        listing_url=item['listing_url'],
        make=tracked_search.make,
        model=item.get('model') or tracked_search.model,
        year=details.get('year', item['year']),
        engine=details.get('engine', item['engine']),
        transmission=details.get('transmission', ''),
        body_type=details.get('body_type', ''),
        color=details.get('color', ''),
        mileage_km=details.get('mileage_km', item['mileage_km']),
        price_eur=details.get('price_eur', item['price_eur']),
        listing_type=item['listing_type'],
        ta_valid_until=details.get('ta_valid_until'),
        thumbnail_url=item['thumbnail_url'] or '',
        photo_urls=details.get('photo_urls', []),
        description=details.get('description', ''),
    )
    return True


def _today():
    from django.utils import timezone
    return timezone.now().date()
