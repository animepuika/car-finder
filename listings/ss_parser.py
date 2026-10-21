import datetime
import re

import defusedxml.ElementTree as ET
from bs4 import BeautifulSoup

SS_BASE_URL = 'https://www.ss.com'
_BOILERPLATE_TOKENS = {'Apskatīt sludinājumu'}


def parse_rss_feed(xml_text):
    root = ET.fromstring(xml_text)
    return [_parse_rss_item(item) for item in root.findall('./channel/item')]


def _parse_rss_item(item_el):
    listing_url = (item_el.findtext('link') or '').strip()
    description_html = item_el.findtext('description') or ''
    fields = _fields_from_tokens(_tokenize(description_html))

    soup = BeautifulSoup(description_html, 'html.parser')
    img = soup.find('img')
    thumbnail_url = img['src'] if img and img.get('src') else None

    price_eur, listing_type = _parse_price(fields.get('Cena'))

    return {
        'listing_url': listing_url,
        'model': fields.get('Modelis'),
        'year': _parse_year(fields.get('Gads')),
        'engine': fields.get('Tilpums'),
        'mileage_km': _parse_mileage(fields.get('Nobraukums')),
        'price_eur': price_eur,
        'listing_type': listing_type,
        'thumbnail_url': thumbnail_url,
    }


def parse_listing_detail(html_text):
    soup = BeautifulSoup(html_text, 'html.parser')

    fields = {}
    for label_cell in soup.select('td.ads_opt_name'):
        label = label_cell.get_text(strip=True).rstrip(':')
        value_cell = label_cell.find_next_sibling('td', class_='ads_opt')
        if value_cell:
            fields[label] = value_cell.get_text(' ', strip=True).replace('\xa0', ' ').strip()

    price_el = soup.select_one('span.ads_price')
    price_eur, listing_type = _parse_price(price_el.get_text(strip=True)) if price_el else (None, 'for_sale')

    photo_urls = []
    seen = set()
    for img in soup.select('img[src*="i.ss.com/gallery"]'):
        src = img.get('src', '')
        if src.endswith('.t.jpg') and src not in seen:
            seen.add(src)
            photo_urls.append(src[:-len('.t.jpg')] + '.800.jpg')

    description_el = soup.select_one('#msg_div_msg')
    description = description_el.get_text('\n', strip=True) if description_el else ''

    return {
        'year': _parse_year(fields.get('Izlaiduma gads')),
        'engine': fields.get('Motors'),
        'transmission': fields.get('Ātrumkārba'),
        'mileage_km': _parse_mileage(fields.get('Nobraukums, km')),
        'color': fields.get('Krāsa'),
        'body_type': fields.get('Virsbūves tips'),
        'price_eur': price_eur,
        'listing_type': listing_type,
        'photo_urls': photo_urls,
        'description': description,
        'ta_valid_until': _parse_ta_valid_until(fields.get('Tehniskā apskate')),
    }


def parse_listing_rows(html_text):
    """Extract {'listing_url', 'price_eur'} for each ad row on a category
    results page, in document order, deduped. Used by the backfill command
    so it can skip over-ceiling ads without fetching their detail pages.
    Only matches the real listing-detail path (/msg/lv/transport/cars/...) -
    ss.com's honeypot links use a different, obfuscated path and are never
    matched. price_eur is None when the row's price cell shows no amount
    (the price is always the row's last cell)."""
    soup = BeautifulSoup(html_text, 'html.parser')
    rows = []
    seen = set()
    for tr in soup.select('tr[id^="tr_"]'):
        link = tr.select_one('a[href*="/msg/lv/transport/cars/"]')
        if not link:
            continue
        href = link.get('href', '')
        if not href.endswith('.html'):
            continue
        if href.startswith('/'):
            href = SS_BASE_URL + href
        if href in seen:
            continue
        seen.add(href)
        price_eur, _ = _parse_price(tr.find_all('td')[-1].get_text())
        rows.append({'listing_url': href, 'price_eur': price_eur})
    return rows


def parse_model_from_listing_url(url):
    """The model slug is always the path segment right before the ad's
    code, e.g. .../cars/skoda/fabia/aaa.html -> 'fabia'. Used by the
    backfill command, which has a URL but no RSS item to read a model
    field from."""
    match = re.search(r'/cars/[^/]+/([^/]+)/[^/]+\.html$', url)
    return match.group(1) if match else None


def _parse_ta_valid_until(value):
    if not value:
        return None
    match = re.match(r'(\d{1,2})\.(\d{4})', value)
    if not match:
        return None
    month, year = int(match.group(1)), int(match.group(2))
    if not 1 <= month <= 12:
        return None
    if month == 12:
        return datetime.date(year + 1, 1, 1) - datetime.timedelta(days=1)
    return datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)


def _tokenize(description_html):
    soup = BeautifulSoup(description_html, 'html.parser')
    tokens = [t for t in soup.get_text('\n', strip=True).split('\n') if t]
    return [t for t in tokens if t not in _BOILERPLATE_TOKENS]


def _fields_from_tokens(tokens):
    """Group a flat token stream into {label: value} pairs, where a label
    is any token ending in ':' and its value is every token up to the
    next label. Handles ss.com's inconsistent <b> nesting because it
    works on flattened text, not raw tag structure."""
    fields = {}
    label = None
    values = []
    for token in tokens:
        if token.endswith(':'):
            if label:
                fields[label] = ' '.join(values).strip()
            label = token[:-1]
            values = []
        else:
            values.append(token)
    if label:
        fields[label] = ' '.join(values).strip()
    return fields


def _parse_year(value):
    if not value:
        return None
    match = re.match(r'(\d{4})', value)
    return int(match.group(1)) if match else None


def _parse_mileage(value):
    if not value:
        return None
    digits = re.sub(r'\D', '', value)
    if not digits:
        return None
    km = int(digits)
    if 'tūkst' in value:
        km *= 1000
    return km


def _parse_price(value):
    if not value:
        return None, 'for_sale'
    if 'pērku' in value.lower():
        return None, 'wanted'
    digits = re.sub(r'[^\d]', '', value)
    return (int(digits) if digits else None), 'for_sale'
