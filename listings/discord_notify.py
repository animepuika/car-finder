import os

import requests

WEBHOOK_URL_ENV_VAR = 'DISCORD_WEBHOOK_URL'
TIMEOUT_SECONDS = 10


def notify_new_listing(listing, warn):
    webhook_url = os.environ.get(WEBHOOK_URL_ENV_VAR)
    if not webhook_url:
        return

    price = f'€{listing.price_eur}' if listing.price_eur is not None else 'price on request'
    year = listing.year or '?'
    content = f'**NEW IN** - {listing.make} {listing.model} ({year}) - {price}\n{listing.listing_url}'

    try:
        response = requests.post(webhook_url, json={'content': content}, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
    except requests.RequestException as exc:
        warn(f'Discord notification failed: {exc}')
