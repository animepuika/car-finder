import os

import requests

from listings.discord_bot import listing_to_embed

WEBHOOK_URL_ENV_VAR = 'DISCORD_WEBHOOK_URL'
TIMEOUT_SECONDS = 10


def notify_new_listing(listing, warn):
    webhook_url = os.environ.get(WEBHOOK_URL_ENV_VAR)
    if not webhook_url:
        return

    payload = {
        'content': f'**NEW IN** - {listing.make} {listing.model}',
        'embeds': [listing_to_embed(listing).to_dict()],
    }

    try:
        response = requests.post(webhook_url, json=payload, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
    except requests.RequestException as exc:
        warn(f'Discord notification failed: {exc}')
