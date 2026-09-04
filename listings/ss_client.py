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


def fetch_filtered_page(make, max_price_eur, page=1):
    url = f'{BASE_URL}/lv/transport/cars/{make}/filter/'
    data = {'topt[8][min]': 0, 'topt[8][max]': max_price_eur}
    if page > 1:
        data['page'] = page
    response = requests.post(url, data=data, headers={'User-Agent': USER_AGENT}, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.text
