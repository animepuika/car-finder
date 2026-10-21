import requests

BASE_URL = 'https://www.ss.com'
USER_AGENT = 'car-finder-personal-tool/1.0 (personal use, low request volume)'
TIMEOUT_SECONDS = 15


def fetch_rss(make, model=None):
    if model:
        url = f'{BASE_URL}/lv/transport/cars/{make}/{model}/rss/'
    else:
        url = f'{BASE_URL}/lv/transport/cars/{make}/rss/'
    response = requests.get(url, headers={'User-Agent': USER_AGENT}, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.text


def fetch_listing_page(url):
    response = requests.get(url, headers={'User-Agent': USER_AGENT}, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.text


def fetch_for_sale_page(make, page=1):
    """One page (30 ads, newest first) of a make's for-sale category.
    ss.com's price filter is session-bound and doesn't apply to a plain
    HTTP client, so callers filter by price from the parsed rows instead."""
    suffix = f'page{page}.html' if page > 1 else ''
    url = f'{BASE_URL}/lv/transport/cars/{make}/sell/{suffix}'
    response = requests.get(url, headers={'User-Agent': USER_AGENT}, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.text
