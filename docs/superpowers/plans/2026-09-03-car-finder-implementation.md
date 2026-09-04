# Car Finder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Django app that automatically tracks chosen car makes (whole brand or one model), applies a price ceiling and an optional "must have valid technical inspection" requirement, and displays matching listings (photo, specs, price) on one page - covering both new listings going forward and what is already posted.

**Architecture:** A scheduled Django management command polls ss.com's per-model or per-brand RSS feeds for new listings, enriches them by fetching their detail page, and stores everything in SQLite. A separate, on-demand backfill command uses ss.com's real price-filter endpoint to pull in the already-existing inventory that RSS's recent-only window would otherwise miss. A single server-rendered view displays and filters what has been found. Django admin manages which makes/models are tracked and their price/TA requirements.

**Tech Stack:** Django 5.2, SQLite, requests, beautifulsoup4, defusedxml. No JS framework, no build step, no CDNs.

**Spec:** `docs/superpowers/specs/2026-09-03-car-finder-design.md`

## Global Constraints

- Data source is ss.com only for v1 (no other sites).
- Single user, no accounts, no public submissions.
- SQLite for storage.
- Django admin is the interface for managing tracked makes/models (`TrackedSearch`).
- Fetching runs on a schedule (Windows Task Scheduler), every 20-30 minutes, not on every page load.
- `listing_type` (`for_sale` vs `wanted`) must be respected everywhere listings are displayed or counted; "wanted" posts are not cars for sale.
- `TrackedSearch.max_price_eur` and `.require_ta` are fetch-time exclusions (skip before saving), not display filters - see Task 2. Year/mileage remain display-time filters only.
- No price history, no notifications/alerts, no active re-verification pass for stale listings, no multi-user accounts. Do not build these.
- Only the two verified ss.com mechanisms are used: RSS feeds and the real price-filter POST endpoint (confirmed live during design research). Never follow a link found on a page without confirming it matches one of these - ss.com has at least one honeypot link (`/fDgSeF4*.html` pattern) matching what robots.txt disallows.
- Do not fetch or store seller phone numbers, VIN codes, or license plates. ss.com gates these behind a JS-driven reveal action specifically (confirmed during design research), and the app has no use for them.

---

### Task 1: Project scaffold

**Files:**
- Create: `manage.py`, `carfinder/__init__.py`, `carfinder/settings.py`, `carfinder/urls.py`, `carfinder/wsgi.py`, `carfinder/asgi.py` (via `django-admin startproject`)
- Create: `listings/__init__.py`, `listings/apps.py` (via `manage.py startapp`)
- Create: `requirements.txt`
- Create: `.gitignore`
- Modify: `carfinder/settings.py` (add `listings` to `INSTALLED_APPS`)
- Modify: `carfinder/urls.py` (wire in `listings.urls`, added in Task 7)

**Interfaces:**
- Produces: a working Django project at the repo root, `listings` app installed, ready for models/views/commands in later tasks.

- [ ] **Step 1: Create virtualenv and install dependencies**

```bash
cd ~/Desktop/car-finder
python -m venv .venv
.venv/Scripts/python.exe -m pip install django requests beautifulsoup4 defusedxml
```

- [ ] **Step 2: Write requirements.txt**

```
Django>=5.2,<5.3
requests>=2.31
beautifulsoup4>=4.12
defusedxml>=0.7
```

- [ ] **Step 3: Scaffold the Django project and app**

```bash
.venv/Scripts/python.exe -m django startproject carfinder .
.venv/Scripts/python.exe manage.py startapp listings
```

- [ ] **Step 4: Register the app**

In `carfinder/settings.py`, add `'listings'` to `INSTALLED_APPS`.

- [ ] **Step 5: Write .gitignore**

```
.venv/
__pycache__/
*.pyc
db.sqlite3
```

- [ ] **Step 6: Verify the project runs**

```bash
.venv/Scripts/python.exe manage.py check
.venv/Scripts/python.exe manage.py migrate
```

Expected: both commands complete with no errors (the second creates `db.sqlite3` with Django's built-in tables).

- [ ] **Step 7: Commit**

```bash
git add manage.py carfinder listings requirements.txt .gitignore
git commit -m "Scaffold Django project and listings app"
```

---

### Task 2: Data model - TrackedSearch and CarListing

**Files:**
- Modify: `listings/models.py`
- Create: `listings/admin.py`
- Create: `listings/tests/__init__.py`
- Create: `listings/tests/test_models.py`
- Create: `listings/migrations/0001_initial.py` (generated)

**Interfaces:**
- Produces: `TrackedSearch(make, model, max_price_eur, require_ta, active)` and `CarListing(tracked_search, listing_url, make, model, year, engine, transmission, body_type, color, mileage_km, price_eur, listing_type, ta_valid_until, thumbnail_url, photo_urls, description, first_seen_at, last_seen_at)`, plus `CarListing.primary_photo_url`, `CarListing.probably_sold`, and `CarListing.has_valid_ta` properties. `listing_type` is one of `CarListing.FOR_SALE` / `CarListing.WANTED`. `TrackedSearch.model` blank means the whole brand.
- Consumes: nothing (base layer).

- [ ] **Step 1: Write failing tests for TrackedSearch**

`listings/tests/__init__.py` (empty file).

`listings/tests/test_models.py`:

```python
import datetime

from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from listings.models import TrackedSearch, CarListing


class TrackedSearchTests(TestCase):
    def test_make_model_pair_is_unique(self):
        TrackedSearch.objects.create(make='volkswagen', model='golf-3')
        with self.assertRaises(IntegrityError):
            TrackedSearch.objects.create(make='volkswagen', model='golf-3')

    def test_model_is_optional_for_brand_wide_tracking(self):
        tracked = TrackedSearch.objects.create(make='skoda', model='', max_price_eur=1200, require_ta=True)
        self.assertEqual(tracked.model, '')


class CarListingHasValidTaTests(TestCase):
    def setUp(self):
        self.tracked = TrackedSearch.objects.create(make='skoda', model='')

    def _listing(self, ta_valid_until):
        return CarListing.objects.create(
            tracked_search=self.tracked, listing_url=f'https://www.ss.com/msg/{ta_valid_until}.html',
            make='skoda', model='fabia', ta_valid_until=ta_valid_until,
        )

    def test_future_ta_date_is_valid(self):
        future = (timezone.now().date() + datetime.timedelta(days=30))
        self.assertTrue(self._listing(future).has_valid_ta)

    def test_past_ta_date_is_not_valid(self):
        past = (timezone.now().date() - datetime.timedelta(days=30))
        self.assertFalse(self._listing(past).has_valid_ta)

    def test_missing_ta_date_is_not_valid(self):
        self.assertFalse(self._listing(None).has_valid_ta)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/Scripts/python.exe manage.py test listings.tests.test_models
```

Expected: FAIL (`TrackedSearch` does not exist yet).

- [ ] **Step 3: Write the models**

`listings/models.py`:

```python
import datetime

from django.db import models
from django.utils import timezone


class TrackedSearch(models.Model):
    make = models.CharField(max_length=50)
    model = models.CharField(max_length=50, blank=True, help_text='Leave blank to track every model of this make.')
    max_price_eur = models.PositiveIntegerField(null=True, blank=True, help_text='Skip listings priced above this. Blank means no limit.')
    require_ta = models.BooleanField(default=False, help_text='Only keep listings with a currently-valid technical inspection.')
    active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('make', 'model')

    def __str__(self):
        return f'{self.make} {self.model}'.strip()


class CarListing(models.Model):
    FOR_SALE = 'for_sale'
    WANTED = 'wanted'
    LISTING_TYPE_CHOICES = [(FOR_SALE, 'For sale'), (WANTED, 'Wanted')]

    STALE_AFTER_DAYS = 14

    tracked_search = models.ForeignKey(TrackedSearch, on_delete=models.CASCADE, related_name='listings')
    listing_url = models.URLField(unique=True)
    make = models.CharField(max_length=50)
    model = models.CharField(max_length=50)
    year = models.PositiveSmallIntegerField(null=True, blank=True)
    engine = models.CharField(max_length=50, blank=True)
    transmission = models.CharField(max_length=50, blank=True)
    body_type = models.CharField(max_length=50, blank=True)
    color = models.CharField(max_length=50, blank=True)
    mileage_km = models.PositiveIntegerField(null=True, blank=True)
    price_eur = models.PositiveIntegerField(null=True, blank=True)
    listing_type = models.CharField(max_length=10, choices=LISTING_TYPE_CHOICES, default=FOR_SALE)
    ta_valid_until = models.DateField(null=True, blank=True)
    thumbnail_url = models.URLField(blank=True)
    photo_urls = models.JSONField(default=list, blank=True)
    description = models.TextField(blank=True)
    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True)

    @property
    def primary_photo_url(self):
        if self.photo_urls:
            return self.photo_urls[0]
        return self.thumbnail_url

    @property
    def probably_sold(self):
        return timezone.now() - self.last_seen_at > datetime.timedelta(days=self.STALE_AFTER_DAYS)

    @property
    def has_valid_ta(self):
        return self.ta_valid_until is not None and self.ta_valid_until >= timezone.now().date()

    def __str__(self):
        return f'{self.make} {self.model} {self.year or "?"} - {self.price_eur or "?"} EUR'
```

- [ ] **Step 4: Make and run migrations**

```bash
.venv/Scripts/python.exe manage.py makemigrations listings
.venv/Scripts/python.exe manage.py migrate
```

- [ ] **Step 5: Run test to verify it passes**

```bash
.venv/Scripts/python.exe manage.py test listings.tests.test_models
```

Expected: PASS.

- [ ] **Step 6: Register admin**

`listings/admin.py`:

```python
from django.contrib import admin

from .models import TrackedSearch, CarListing


@admin.register(TrackedSearch)
class TrackedSearchAdmin(admin.ModelAdmin):
    list_display = ('make', 'model', 'max_price_eur', 'require_ta', 'active')
    list_filter = ('active', 'require_ta')


@admin.register(CarListing)
class CarListingAdmin(admin.ModelAdmin):
    list_display = ('make', 'model', 'year', 'price_eur', 'listing_type', 'ta_valid_until', 'last_seen_at')
    list_filter = ('make', 'listing_type')
    readonly_fields = [f.name for f in CarListing._meta.fields]

    def has_add_permission(self, request):
        return False
```

`CarListing` is admin-visible but not manually editable there - it exists only as output of the fetch command.

- [ ] **Step 7: Create a superuser and verify admin loads**

```bash
.venv/Scripts/python.exe manage.py createsuperuser
```

Then start the dev server via the Browser pane's `preview_start` (add a `car-finder` entry to `.claude/launch.json` pointing at `.venv/Scripts/python.exe manage.py runserver`, port 8000), open `/admin/`, log in, confirm both `Tracked searches` and `Car listings` appear, and that adding a `TrackedSearch` with make `volkswagen` / model `golf-3` works.

- [ ] **Step 8: Commit**

```bash
git add listings/models.py listings/admin.py listings/migrations listings/tests
git commit -m "Add TrackedSearch and CarListing models"
```

---

### Task 3: RSS and listing-detail parsing (ss_parser.py)

This is pure parsing logic - no network, no Django ORM - so it is tested directly against fixture files. The fixtures below use real field values and markup captured from ss.com during design research (a Golf 3 RSS feed, a brand-wide Volkswagen RSS feed, and a real Golf 3 listing detail page), trimmed to the parts the parser reads.

**Files:**
- Create: `listings/ss_parser.py`
- Create: `listings/tests/fixtures/golf3_rss.xml`
- Create: `listings/tests/fixtures/vw_brand_rss.xml`
- Create: `listings/tests/fixtures/golf3_listing_detail.html`
- Create: `listings/tests/test_ss_parser.py`

**Interfaces:**
- Produces: `parse_rss_feed(xml_text: str) -> list[dict]`, each dict having keys `listing_url, model, year, engine, mileage_km, price_eur, listing_type, thumbnail_url` (`model` is `None` when the feed is model-specific and doesn't repeat it - Task 5 falls back to the `TrackedSearch`'s own model in that case). `parse_listing_detail(html_text: str) -> dict` with keys `year, engine, transmission, mileage_km, color, body_type, price_eur, listing_type, photo_urls, description, ta_valid_until` - these keys match `CarListing` field names exactly (plus `listing_type`, which Task 6's backfill needs since it has no RSS item to read that from), since Task 5 and Task 6 assign them directly. `parse_listing_urls(html_text: str) -> list[str]` extracts listing URLs from a price-filtered category results page. `parse_model_from_listing_url(url: str) -> str | None` reads the model slug out of a listing URL. Both of the last two are for the backfill command in Task 6.
- Consumes: nothing (pure functions over text).

- [ ] **Step 1: Write the fixture files**

`listings/tests/fixtures/golf3_rss.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>Sludinājumi - SS.COM - RSS. Transports : Vieglie auto : Volkswagen : Golf 3, Cenas</title>
<link>https://www.ss.com/lv/transport/cars/volkswagen/golf-3/</link>
<description>Sludinājumi - SS.COM - RSS. Transports : Vieglie auto : Volkswagen : Golf 3, Cenas</description>
<lastBuildDate>Thu, 03 Sep 2026 17:01:12 +0300</lastBuildDate>
<ttl>5</ttl>
<item>
<title><![CDATA[ Automāts. 300eur Pirmā iemaksa. ]]></title>
<link>https://www.ss.com/msg/lv/transport/cars/volkswagen/golf-3/ckjje.html</link>
<pubDate>Wed, 02 Sep 2026 21:11:55 +0300</pubDate>
<description><![CDATA[ <a href="https://www.ss.com/msg/lv/transport/cars/volkswagen/golf-3/ckjje.html"><img align=right border=0 src="https://i.ss.com/gallery/8/1540/384904/76980748.t.jpg" width="174" height="130" alt=""></a> Gads: <b>1997</b><br/>Tilpums: <b>1.8</b><br/>Cena: <b>1,500 €</b><br/><br/><b><a href="https://www.ss.com/msg/lv/transport/cars/volkswagen/golf-3/ckjje.html">Apskatīt sludinājumu</a></b><br/><br/> ]]></description>
</item>
<item>
<title><![CDATA[ 1,9 tdi 66kw, degvielas patēriņš 4l/100km. ]]></title>
<link>https://www.ss.com/msg/lv/transport/cars/volkswagen/golf-3/cfojc.html</link>
<pubDate>Wed, 02 Sep 2026 13:43:01 +0300</pubDate>
<description><![CDATA[ <a href="https://www.ss.com/msg/lv/transport/cars/volkswagen/golf-3/cfojc.html"><img align=right border=0 src="https://i.ss.com/gallery/8/1540/384910/76981883.t.jpg" width="174" height="130" alt=""></a> Gads: <b><b>1995</b></b><br/>Tilpums: <b><b>1.9D</b></b><br/>Nobraukums: <b><b>252</b> tūkst.</b><br/>Cena: <b><b>950</b> €</b><br/><br/><b><a href="https://www.ss.com/msg/lv/transport/cars/volkswagen/golf-3/cfojc.html">Apskatīt sludinājumu</a></b><br/><br/> ]]></description>
</item>
<item>
<title><![CDATA[ Покупаю, A/m Volkswagen Golf 3 uz izjaukšanu. ]]></title>
<link>https://www.ss.com/msg/lv/transport/cars/volkswagen/golf-3/deofm.html</link>
<pubDate>Wed, 26 Aug 2026 23:17:25 +0300</pubDate>
<description><![CDATA[ <a href="https://www.ss.com/msg/lv/transport/cars/volkswagen/golf-3/deofm.html"><img align=right border=0 src="https://i.ss.com/gallery/1/2/255/50832.t.jpg" width="174" height="130" alt=""></a> Cena: <b><b>pērku</b> </b><br/><br/><b><a href="https://www.ss.com/msg/lv/transport/cars/volkswagen/golf-3/deofm.html">Apskatīt sludinājumu</a></b><br/><br/> ]]></description>
</item>
</channel>
</rss>
```

`listings/tests/fixtures/vw_brand_rss.xml` (the brand-wide feed - same structure, but items carry a `Modelis` field since it isn't implied by the URL; real data from `ss.com/lv/transport/cars/volkswagen/rss/`):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>Sludinājumi - SS.COM - RSS. Transports : Vieglie auto : Volkswagen, Cenas</title>
<link>https://www.ss.com/lv/transport/cars/volkswagen/</link>
<description>Sludinājumi - SS.COM - RSS. Transports : Vieglie auto : Volkswagen, Cenas</description>
<lastBuildDate>Fri, 04 Sep 2026 12:07:21 +0300</lastBuildDate>
<ttl>5</ttl>
<item>
<title><![CDATA[ VW Touran 1.9d 77kw, ar jaunu tehnisko apskati. ]]></title>
<link>https://www.ss.com/msg/lv/transport/cars/volkswagen/touran/cefgfx.html</link>
<pubDate>Fri, 04 Sep 2026 12:06:55 +0300</pubDate>
<description><![CDATA[ <a href="https://www.ss.com/msg/lv/transport/cars/volkswagen/touran/cefgfx.html"><img align=right border=0 src="https://i.ss.com/gallery/8/1538/384370/76873847.t.jpg" width="174" height="130" alt=""></a> Modelis: <b><b>Touran</b></b><br/>Gads: <b><b>2010</b></b><br/>Tilpums: <b><b>1.9D</b></b><br/>Nobraukums: <b><b>314</b> tūkst.</b><br/>Cena: <b><b>1,650</b> €</b><br/><br/><b><a href="https://www.ss.com/msg/lv/transport/cars/volkswagen/touran/cefgfx.html">Apskatīt sludinājumu</a></b><br/><br/> ]]></description>
</item>
<item>
<title><![CDATA[ Volkswagen Touareg 3.0Tdi (231zs). ]]></title>
<link>https://www.ss.com/msg/lv/transport/cars/volkswagen/touareg/alefo.html</link>
<pubDate>Fri, 04 Sep 2026 11:50:48 +0300</pubDate>
<description><![CDATA[ <a href="https://www.ss.com/msg/lv/transport/cars/volkswagen/touareg/alefo.html"><img align=right border=0 src="https://i.ss.com/gallery/8/1487/371525/74304951.t.jpg" width="174" height="130" alt=""></a> Modelis: <b>Touareg</b><br/>Gads: <b>2025</b><br/>Tilpums: <b>3.0D</b><br/>Nobraukums: <b>19 tūkst.</b><br/>Cena: <b>56,850 €</b><br/><br/><b><a href="https://www.ss.com/msg/lv/transport/cars/volkswagen/touareg/alefo.html">Apskatīt sludinājumu</a></b><br/><br/> ]]></description>
</item>
</channel>
</rss>
```

`listings/tests/fixtures/golf3_listing_detail.html` (the specs table, price, description and gallery images with real classes/ids from a live ss.com listing page; unrelated page chrome omitted). Includes the "Tehniskā apskate" row - same `ads_opt_name`/`ads_opt` structure as every other spec row, from the same real page:

```html
<html><body>
<table>
<tr><td height="28" class="ads_opt_name" width="30" nowrap="">Marka <img src="https://i.ss.com/img/alogo/volkswagen.gif" width="48" height="24"></td><td class="ads_opt" id="tdo_31" nowrap=""><b>Volkswagen Golf 3</b></td></tr>
<tr><td height="20" class="ads_opt_name" width="30" nowrap="">Izlaiduma gads:</td><td class="ads_opt" id="tdo_18" nowrap="">2000 maijs</td></tr>
<tr><td height="20" class="ads_opt_name" width="30" nowrap="">Motors:</td><td class="ads_opt" id="tdo_15" nowrap="">1.9 dīzelis</td></tr>
<tr><td height="20" class="ads_opt_name" width="30" nowrap="">Ātrumkārba:</td><td class="ads_opt" id="tdo_35" nowrap="">Manuāla 5 ātrumi</td></tr>
<tr><td height="20" class="ads_opt_name" width="30" nowrap="">Nobraukums, km:</td><td class="ads_opt" id="tdo_16" nowrap="">264 231</td></tr>
<tr><td height="20" class="ads_opt_name" width="30" nowrap="">Krāsa:</td><td class="ads_opt" id="tdo_17" nowrap="">Zila <div class="ads_color_opt" style="background-color:#000099;">&nbsp;</div></td></tr>
<tr><td height="20" class="ads_opt_name" width="30" nowrap="">Virsbūves tips:</td><td class="ads_opt" id="tdo_32" nowrap="">Kabriolets</td></tr>
<tr><td height="20" class="ads_opt_name" width="30" nowrap="">Tehniskā apskate:</td><td class="ads_opt" id="tdo_223" nowrap="">06.2027</td></tr>
</table>
<span class="ads_price" id="tdo_8">1 900 €</span>
<div id="msg_div_msg">Pārdodu VW Golf Cabriolet ar uzticamo 1.9 TDI 81 kW dzinēju. Auto ir labā tehniskā un vizuālā stāvoklī, ieguldījumi nav nepieciešami.</div>
<img src="https://i.ss.com/gallery/8/1525/381069/volkswagen-golf-3-76213628.800.jpg">
<img src="https://i.ss.com/gallery/8/1525/381069/volkswagen-golf-3-76213628.t.jpg">
<img src="https://i.ss.com/gallery/8/1525/381069/volkswagen-golf-3-76213629.t.jpg">
<img src="https://i.ss.com/gallery/8/1525/381069/volkswagen-golf-3-76213630.t.jpg">
<img src="https://i.ss.com/gallery/8/1525/381069/volkswagen-golf-3-76213631.t.jpg">
</body></html>
```

- [ ] **Step 2: Write the failing tests**

`listings/tests/test_ss_parser.py`:

```python
import datetime
import os

from django.test import SimpleTestCase

from listings import ss_parser

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')


def _read_fixture(name):
    with open(os.path.join(FIXTURES_DIR, name), encoding='utf-8') as f:
        return f.read()


class ParseRssFeedTests(SimpleTestCase):
    def setUp(self):
        self.xml_text = _read_fixture('golf3_rss.xml')

    def test_parses_three_items(self):
        items = ss_parser.parse_rss_feed(self.xml_text)
        self.assertEqual(len(items), 3)

    def test_for_sale_listing_without_mileage(self):
        items = ss_parser.parse_rss_feed(self.xml_text)
        item = next(i for i in items if i['listing_url'].endswith('ckjje.html'))
        self.assertEqual(item['year'], 1997)
        self.assertEqual(item['engine'], '1.8')
        self.assertIsNone(item['mileage_km'])
        self.assertEqual(item['price_eur'], 1500)
        self.assertEqual(item['listing_type'], 'for_sale')
        self.assertTrue(item['thumbnail_url'].endswith('76980748.t.jpg'))

    def test_for_sale_listing_with_mileage_in_thousands(self):
        items = ss_parser.parse_rss_feed(self.xml_text)
        item = next(i for i in items if i['listing_url'].endswith('cfojc.html'))
        self.assertEqual(item['mileage_km'], 252000)
        self.assertEqual(item['price_eur'], 950)

    def test_wanted_listing_has_no_price_or_specs(self):
        items = ss_parser.parse_rss_feed(self.xml_text)
        item = next(i for i in items if i['listing_url'].endswith('deofm.html'))
        self.assertEqual(item['listing_type'], 'wanted')
        self.assertIsNone(item['price_eur'])
        self.assertIsNone(item['year'])

    def test_model_specific_feed_has_no_model_field(self):
        items = ss_parser.parse_rss_feed(self.xml_text)
        self.assertTrue(all(item['model'] is None for item in items))


class ParseBrandRssFeedTests(SimpleTestCase):
    def test_brand_wide_feed_includes_model_per_item(self):
        xml_text = _read_fixture('vw_brand_rss.xml')
        items = ss_parser.parse_rss_feed(xml_text)
        by_url = {i['listing_url']: i for i in items}
        touran = by_url['https://www.ss.com/msg/lv/transport/cars/volkswagen/touran/cefgfx.html']
        touareg = by_url['https://www.ss.com/msg/lv/transport/cars/volkswagen/touareg/alefo.html']
        self.assertEqual(touran['model'], 'Touran')
        self.assertEqual(touran['price_eur'], 1650)
        self.assertEqual(touareg['model'], 'Touareg')
        self.assertEqual(touareg['price_eur'], 56850)


class ParseListingDetailTests(SimpleTestCase):
    def test_parses_full_specs(self):
        html_text = _read_fixture('golf3_listing_detail.html')
        details = ss_parser.parse_listing_detail(html_text)
        self.assertEqual(details['year'], 2000)
        self.assertEqual(details['engine'], '1.9 dīzelis')
        self.assertEqual(details['transmission'], 'Manuāla 5 ātrumi')
        self.assertEqual(details['mileage_km'], 264231)
        self.assertEqual(details['color'], 'Zila')
        self.assertEqual(details['body_type'], 'Kabriolets')
        self.assertEqual(details['price_eur'], 1900)
        self.assertEqual(len(details['photo_urls']), 4)
        self.assertIn('Pārdodu VW Golf Cabriolet', details['description'])

    def test_parses_ta_valid_until_as_last_day_of_month(self):
        html_text = _read_fixture('golf3_listing_detail.html')
        details = ss_parser.parse_listing_detail(html_text)
        self.assertEqual(details['ta_valid_until'], datetime.date(2027, 6, 30))

    def test_missing_ta_row_gives_none(self):
        html_text = _read_fixture('golf3_listing_detail.html').replace(
            '<tr><td height="20" class="ads_opt_name" width="30" nowrap="">Tehniskā apskate:</td><td class="ads_opt" id="tdo_223" nowrap="">06.2027</td></tr>',
            '',
        )
        details = ss_parser.parse_listing_detail(html_text)
        self.assertIsNone(details['ta_valid_until'])

    def test_detail_page_reports_wanted_listing_type(self):
        html_text = _read_fixture('golf3_listing_detail.html').replace(
            '<span class="ads_price" id="tdo_8">1 900 €</span>', '<span class="ads_price" id="tdo_8">pērku</span>',
        )
        details = ss_parser.parse_listing_detail(html_text)
        self.assertEqual(details['listing_type'], 'wanted')
        self.assertIsNone(details['price_eur'])


class ParseListingUrlsTests(SimpleTestCase):
    def test_extracts_unique_listing_urls_from_a_results_page(self):
        html_text = '''
        <html><body>
        <a href="/msg/lv/transport/cars/skoda/fabia/aaa.html">Fabia</a>
        <a href="/msg/lv/transport/cars/skoda/octavia/bbb.html">Octavia</a>
        <a href="/msg/lv/transport/cars/skoda/fabia/aaa.html">Fabia (photo link, same ad)</a>
        <a href="/lv/transport/cars/skoda/fDgSeF4belM=.html">honeypot, must be ignored</a>
        </body></html>
        '''
        urls = ss_parser.parse_listing_urls(html_text)
        self.assertEqual(urls, [
            'https://www.ss.com/msg/lv/transport/cars/skoda/fabia/aaa.html',
            'https://www.ss.com/msg/lv/transport/cars/skoda/octavia/bbb.html',
        ])


class ParseModelFromListingUrlTests(SimpleTestCase):
    def test_extracts_model_slug(self):
        url = 'https://www.ss.com/msg/lv/transport/cars/skoda/fabia/aaa.html'
        self.assertEqual(ss_parser.parse_model_from_listing_url(url), 'fabia')

    def test_returns_none_for_an_unrecognised_url(self):
        self.assertIsNone(ss_parser.parse_model_from_listing_url('https://www.ss.com/lv/transport/cars/skoda/'))
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
.venv/Scripts/python.exe manage.py test listings.tests.test_ss_parser
```

Expected: FAIL (`listings.ss_parser` does not exist yet).

- [ ] **Step 4: Write the parser**

`listings/ss_parser.py` (verified against the fixtures above during design; see design research notes in the spec):

```python
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
            photo_urls.append(src)

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


def parse_listing_urls(html_text):
    """Extract listing URLs from a category/filtered results page, in
    document order, deduped. Used by the backfill command. Only matches
    the real listing-detail path (/msg/lv/transport/cars/...) - ss.com's
    honeypot links use a different, obfuscated path and are never matched."""
    soup = BeautifulSoup(html_text, 'html.parser')
    urls = []
    seen = set()
    for a in soup.select('a[href*="/msg/lv/transport/cars/"]'):
        href = a.get('href', '')
        if not href.endswith('.html'):
            continue
        if href.startswith('/'):
            href = SS_BASE_URL + href
        if href not in seen:
            seen.add(href)
            urls.append(href)
    return urls


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
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
.venv/Scripts/python.exe manage.py test listings.tests.test_ss_parser
```

Expected: PASS, all 13 tests.

- [ ] **Step 6: Commit**

```bash
git add listings/ss_parser.py listings/tests/fixtures listings/tests/test_ss_parser.py
git commit -m "Add RSS and listing-detail parsing for ss.com"
```

---

### Task 4: Network client (ss_client.py)

**Files:**
- Create: `listings/ss_client.py`

**Interfaces:**
- Produces: `fetch_rss(make: str, model: str | None) -> str` (raw XML text; brand-wide feed when `model` is falsy), `fetch_listing_page(url: str) -> str` (raw HTML text), `fetch_filtered_page(make: str, max_price_eur: int, page: int = 1) -> str` (raw HTML of a price-filtered category results page, for the backfill command in Task 6). All raise `requests.RequestException` on failure - callers handle that.
- Consumes: nothing.

This is a thin I/O wrapper with no branching logic worth unit-testing in isolation; it is exercised through Task 5's mocked command tests and Task 9's real end-to-end run.

- [ ] **Step 1: Write the client**

`listings/ss_client.py`:

```python
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
```

`topt[8][min]`/`topt[8][max]` are the real field names ss.com's own price-filter form submits (confirmed by filling and submitting the form during design research, not guessed). The `page` parameter is a placeholder for whatever pagination ss.com actually uses past the first page - not confirmed during design research, so Task 6 verifies this live against a real filtered result set before relying on it.

- [ ] **Step 2: Verify it works against the real site**

```bash
.venv/Scripts/python.exe manage.py shell -c "from listings import ss_client; print(ss_client.fetch_rss('volkswagen')[:200]); print(ss_client.fetch_rss('volkswagen', 'golf-3')[:200])"
```

Expected: prints the start of two real RSS XML documents, the first mixing models, the second Golf 3 only.

- [ ] **Step 3: Commit**

```bash
git add listings/ss_client.py
git commit -m "Add ss.com network client"
```

---

### Task 5: fetch_listings management command

**Files:**
- Create: `listings/management/__init__.py`
- Create: `listings/management/commands/__init__.py`
- Create: `listings/management/commands/fetch_listings.py`
- Create: `listings/tests/test_fetch_listings.py`

**Interfaces:**
- Consumes: `ss_client.fetch_rss`, `ss_client.fetch_listing_page`, `ss_parser.parse_rss_feed`, `ss_parser.parse_listing_detail`, `TrackedSearch`, `CarListing` from earlier tasks.
- Produces: the `fetch_listings` management command (`manage.py fetch_listings`), and `listings/listing_sync.py`'s `save_new_listing(tracked_search, item, warn)` function it's built on. Task 6's backfill command does not reuse this - see Task 6 for why - but both apply the same price/TA rules from `TrackedSearch`.

- [ ] **Step 1: Write the failing tests**

`listings/tests/test_fetch_listings.py`:

```python
import os
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from listings.models import TrackedSearch, CarListing

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')


def _read_fixture(name):
    with open(os.path.join(FIXTURES_DIR, name), encoding='utf-8') as f:
        return f.read()


class FetchListingsCommandTests(TestCase):
    def setUp(self):
        self.tracked = TrackedSearch.objects.create(make='volkswagen', model='golf-3', active=True)
        self.rss_fixture = _read_fixture('golf3_rss.xml')
        self.detail_fixture = _read_fixture('golf3_listing_detail.html')

    @patch('listings.management.commands.fetch_listings.ss_client')
    def test_creates_listings_split_by_type(self, mock_client):
        mock_client.fetch_rss.return_value = self.rss_fixture
        mock_client.fetch_listing_page.return_value = self.detail_fixture

        call_command('fetch_listings')

        self.assertEqual(CarListing.objects.filter(listing_type='for_sale').count(), 2)
        self.assertEqual(CarListing.objects.filter(listing_type='wanted').count(), 1)

    @patch('listings.management.commands.fetch_listings.ss_client')
    def test_second_run_does_not_duplicate(self, mock_client):
        mock_client.fetch_rss.return_value = self.rss_fixture
        mock_client.fetch_listing_page.return_value = self.detail_fixture

        call_command('fetch_listings')
        call_command('fetch_listings')

        self.assertEqual(CarListing.objects.count(), 3)

    @patch('listings.management.commands.fetch_listings.ss_client')
    def test_detail_fetch_failure_still_saves_rss_data(self, mock_client):
        mock_client.fetch_rss.return_value = self.rss_fixture
        mock_client.fetch_listing_page.side_effect = Exception('network error')

        call_command('fetch_listings')

        listing = CarListing.objects.get(listing_url__endswith='ckjje.html')
        self.assertEqual(listing.year, 1997)
        self.assertEqual(listing.price_eur, 1500)

    @patch('listings.management.commands.fetch_listings.ss_client')
    def test_one_failing_tracked_search_does_not_block_others(self, mock_client):
        TrackedSearch.objects.create(make='bmw', model='e30', active=True)

        def fetch_rss_side_effect(make, model=None):
            if make == 'bmw':
                raise Exception('site unreachable')
            return self.rss_fixture

        mock_client.fetch_rss.side_effect = fetch_rss_side_effect
        mock_client.fetch_listing_page.return_value = self.detail_fixture

        call_command('fetch_listings')

        self.assertEqual(CarListing.objects.filter(tracked_search=self.tracked).count(), 3)

    @patch('listings.management.commands.fetch_listings.ss_client')
    def test_brand_wide_search_uses_rss_model_field(self, mock_client):
        TrackedSearch.objects.create(make='volkswagen', model='', active=True)
        mock_client.fetch_rss.return_value = _read_fixture('vw_brand_rss.xml')
        mock_client.fetch_listing_page.return_value = self.detail_fixture

        call_command('fetch_listings')

        touran = CarListing.objects.get(listing_url__endswith='cefgfx.html')
        self.assertEqual(touran.model, 'Touran')

    @patch('listings.management.commands.fetch_listings.ss_client')
    def test_price_over_ceiling_is_skipped_without_a_detail_fetch(self, mock_client):
        self.tracked.max_price_eur = 1000
        self.tracked.save()
        single_expensive_item_rss = '''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<item>
<title><![CDATA[ Automāts. 300eur Pirmā iemaksa. ]]></title>
<link>https://www.ss.com/msg/lv/transport/cars/volkswagen/golf-3/ckjje.html</link>
<pubDate>Wed, 02 Sep 2026 21:11:55 +0300</pubDate>
<description><![CDATA[ <a href="https://www.ss.com/msg/lv/transport/cars/volkswagen/golf-3/ckjje.html"><img align=right border=0 src="https://i.ss.com/gallery/8/1540/384904/76980748.t.jpg" width="174" height="130" alt=""></a> Gads: <b>1997</b><br/>Tilpums: <b>1.8</b><br/>Cena: <b>1,500 €</b><br/><br/> ]]></description>
</item>
</channel></rss>'''
        mock_client.fetch_rss.return_value = single_expensive_item_rss

        call_command('fetch_listings')

        self.assertFalse(CarListing.objects.filter(listing_url__endswith='ckjje.html').exists())
        mock_client.fetch_listing_page.assert_not_called()

    @patch('listings.management.commands.fetch_listings.ss_client')
    def test_require_ta_excludes_listings_without_valid_ta(self, mock_client):
        self.tracked.require_ta = True
        self.tracked.save()
        no_ta_detail = self.detail_fixture.replace(
            '<tr><td height="20" class="ads_opt_name" width="30" nowrap="">Tehniskā apskate:</td><td class="ads_opt" id="tdo_223" nowrap="">06.2027</td></tr>',
            '',
        )
        mock_client.fetch_rss.return_value = self.rss_fixture
        mock_client.fetch_listing_page.return_value = no_ta_detail

        call_command('fetch_listings')

        self.assertEqual(CarListing.objects.filter(listing_type='for_sale').count(), 0)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/Scripts/python.exe manage.py test listings.tests.test_fetch_listings
```

Expected: FAIL (command does not exist yet).

- [ ] **Step 3: Write the command**

`listings/management/__init__.py` and `listings/management/commands/__init__.py`: empty files.

`listings/management/commands/fetch_listings.py`:

`listings/listing_sync.py` (the RSS-path save logic, in its own module so `fetch_listings.py` stays focused on orchestration):

```python
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
```

`listings/management/commands/fetch_listings.py`:

```python
import sys

from django.core.management.base import BaseCommand

from listings import ss_client, ss_parser
from listings.listing_sync import save_new_listing
from listings.models import TrackedSearch


class Command(BaseCommand):
    help = "Fetch new car listings from ss.com for all active tracked searches"

    def handle(self, *args, **options):
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')

        for tracked_search in TrackedSearch.objects.filter(active=True):
            try:
                self._fetch_for_search(tracked_search)
            except Exception as exc:
                self.stderr.write(self.style.ERROR(f'Failed to fetch {tracked_search}: {exc}'))

    def _fetch_for_search(self, tracked_search):
        xml_text = ss_client.fetch_rss(tracked_search.make, tracked_search.model or None)
        items = ss_parser.parse_rss_feed(xml_text)

        new_count = 0
        for item in items:
            created = save_new_listing(
                tracked_search, item,
                warn=lambda msg: self.stderr.write(self.style.WARNING(msg)),
            )
            if created:
                new_count += 1

        self.stdout.write(self.style.SUCCESS(f'{tracked_search}: {len(items)} seen, {new_count} new'))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/Scripts/python.exe manage.py test listings.tests.test_fetch_listings
```

Expected: PASS, all 7 tests. Note that "wanted" posts never trigger a detail-page fetch in this version - there's nothing to enrich them with since they're never displayed, so skipping it saves a request. This is a deliberate change from fetching every new listing's detail page regardless of type.

- [ ] **Step 5: Commit**

```bash
git add listings/listing_sync.py listings/management listings/tests/test_fetch_listings.py
git commit -m "Add fetch_listings management command"
```

---

### Task 6: Backfill existing listings

RSS only shows recent activity, so a brand-wide `TrackedSearch` needs a separate way to pick up what is already listed. This command uses ss.com's real price-filter endpoint (confirmed in Task 4) to get the actual current inventory, not just what happened to still be in RSS's recent window.

Deliberately kept separate from `fetch_listings` rather than forced to share its save logic: the RSS path gets a cheap price pre-check straight from the feed before ever fetching a detail page, but backfill only ever has a bare URL, so every one of them needs a detail-page fetch regardless - there is no equivalent cheap check available for that path. Trying to force one shared function to cover both made the price/TA logic harder to follow, not easier, so this task accepts a small amount of duplication with Task 5's `listing_sync.save_new_listing` instead.

**Files:**
- Create: `listings/management/commands/backfill_listings.py`
- Create: `listings/tests/fixtures/skoda_filter_results.html`
- Create: `listings/tests/test_backfill_listings.py`

**Interfaces:**
- Consumes: `ss_client.fetch_filtered_page`, `ss_client.fetch_listing_page`, `ss_parser.parse_listing_urls`, `ss_parser.parse_listing_detail`, `ss_parser.parse_model_from_listing_url`, `TrackedSearch`, `CarListing` from earlier tasks.
- Produces: the `backfill_listings` management command (`manage.py backfill_listings`), callable via `call_command`.

- [ ] **Step 1: Write the fixture**

`listings/tests/fixtures/skoda_filter_results.html` (a trimmed results page in the same link shape as a real ss.com category/filter page; reuses two real listing URLs already captured for other fixtures plus one honeypot-shaped link, which must never be followed):

```html
<html><body>
<div class="results">
<a href="/msg/lv/transport/cars/volkswagen/golf-3/ckjje.html"><img src="https://i.ss.com/gallery/8/1540/384904/76980748.t.jpg"></a>
<a href="/msg/lv/transport/cars/volkswagen/golf-3/ckjje.html">Automāts. 300eur Pirmā iemaksa.</a>
<a href="/msg/lv/transport/cars/volkswagen/golf-3/cfojc.html"><img src="https://i.ss.com/gallery/8/1540/384910/76981883.t.jpg"></a>
<a href="/msg/lv/transport/cars/volkswagen/golf-3/cfojc.html">1,9 tdi 66kw, degvielas patēriņš 4l/100km.</a>
<a href="/lv/transport/cars/skoda/fDgSeF4belM=.html">honeypot, must be ignored</a>
</div>
</body></html>
```

- [ ] **Step 2: Write the failing tests**

`listings/tests/test_backfill_listings.py`:

```python
import os
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from listings.models import TrackedSearch, CarListing

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')


def _read_fixture(name):
    with open(os.path.join(FIXTURES_DIR, name), encoding='utf-8') as f:
        return f.read()


class BackfillListingsCommandTests(TestCase):
    def setUp(self):
        self.tracked = TrackedSearch.objects.create(make='volkswagen', model='', max_price_eur=1200, active=True)
        self.filter_results = _read_fixture('skoda_filter_results.html')
        self.detail_fixture = _read_fixture('golf3_listing_detail.html')

    @patch('listings.management.commands.backfill_listings.ss_client')
    def test_creates_listings_from_filtered_results(self, mock_client):
        mock_client.fetch_filtered_page.return_value = self.filter_results
        mock_client.fetch_listing_page.return_value = self.detail_fixture

        call_command('backfill_listings')

        self.assertEqual(CarListing.objects.count(), 2)
        listing = CarListing.objects.get(listing_url__endswith='ckjje.html')
        self.assertEqual(listing.model, 'golf-3')
        self.assertEqual(listing.price_eur, 1900)

    @patch('listings.management.commands.backfill_listings.ss_client')
    def test_already_known_listings_are_not_refetched(self, mock_client):
        CarListing.objects.create(
            tracked_search=self.tracked,
            listing_url='https://www.ss.com/msg/lv/transport/cars/volkswagen/golf-3/ckjje.html',
            make='volkswagen', model='golf-3', listing_type=CarListing.FOR_SALE,
        )
        mock_client.fetch_filtered_page.return_value = self.filter_results
        mock_client.fetch_listing_page.return_value = self.detail_fixture

        call_command('backfill_listings')

        self.assertEqual(CarListing.objects.count(), 2)
        mock_client.fetch_listing_page.assert_called_once()

    @patch('listings.management.commands.backfill_listings.ss_client')
    def test_require_ta_excludes_listings_without_valid_ta(self, mock_client):
        self.tracked.require_ta = True
        self.tracked.save()
        no_ta_detail = self.detail_fixture.replace(
            '<tr><td height="20" class="ads_opt_name" width="30" nowrap="">Tehniskā apskate:</td><td class="ads_opt" id="tdo_223" nowrap="">06.2027</td></tr>',
            '',
        )
        mock_client.fetch_filtered_page.return_value = self.filter_results
        mock_client.fetch_listing_page.return_value = no_ta_detail

        call_command('backfill_listings')

        self.assertEqual(CarListing.objects.count(), 0)

    @patch('listings.management.commands.backfill_listings.ss_client')
    def test_tracked_search_without_max_price_is_skipped(self, mock_client):
        self.tracked.max_price_eur = None
        self.tracked.save()

        call_command('backfill_listings')

        mock_client.fetch_filtered_page.assert_not_called()
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
.venv/Scripts/python.exe manage.py test listings.tests.test_backfill_listings
```

Expected: FAIL (command does not exist yet).

- [ ] **Step 4: Write the command**

`listings/management/commands/backfill_listings.py`:

```python
import sys
import time

from django.core.management.base import BaseCommand
from django.utils import timezone

from listings import ss_client, ss_parser
from listings.models import CarListing, TrackedSearch

REQUEST_DELAY_SECONDS = 1


class Command(BaseCommand):
    help = "Pull in already-existing ss.com listings for tracked searches with a price ceiling set"

    def handle(self, *args, **options):
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')

        for tracked_search in TrackedSearch.objects.filter(active=True):
            if tracked_search.max_price_eur is None:
                self.stdout.write(f'{tracked_search}: skipped, no max_price_eur set')
                continue
            try:
                new_count = self._backfill_for_search(tracked_search)
                self.stdout.write(self.style.SUCCESS(f'{tracked_search}: {new_count} new from backfill'))
            except Exception as exc:
                self.stderr.write(self.style.ERROR(f'Backfill failed for {tracked_search}: {exc}'))

    def _backfill_for_search(self, tracked_search):
        html = ss_client.fetch_filtered_page(tracked_search.make, tracked_search.max_price_eur)
        urls = ss_parser.parse_listing_urls(html)

        new_count = 0
        for url in urls:
            if self._save_listing(tracked_search, url):
                new_count += 1
        return new_count

    def _save_listing(self, tracked_search, url):
        if CarListing.objects.filter(listing_url=url).exists():
            return False

        try:
            detail_html = ss_client.fetch_listing_page(url)
            details = ss_parser.parse_listing_detail(detail_html)
        except Exception as exc:
            self.stderr.write(self.style.WARNING(f'Detail fetch failed for {url}: {exc}'))
            return False
        finally:
            time.sleep(REQUEST_DELAY_SECONDS)

        if details['listing_type'] != CarListing.FOR_SALE:
            return False

        if tracked_search.require_ta:
            if details['ta_valid_until'] is None or details['ta_valid_until'] < timezone.now().date():
                return False

        CarListing.objects.create(
            tracked_search=tracked_search,
            listing_url=url,
            make=tracked_search.make,
            model=ss_parser.parse_model_from_listing_url(url) or tracked_search.model,
            year=details['year'],
            engine=details['engine'],
            transmission=details['transmission'],
            body_type=details['body_type'],
            color=details['color'],
            mileage_km=details['mileage_km'],
            price_eur=details['price_eur'],
            listing_type=details['listing_type'],
            ta_valid_until=details['ta_valid_until'],
            thumbnail_url=(details['photo_urls'][0] if details['photo_urls'] else ''),
            photo_urls=details['photo_urls'],
            description=details['description'],
        )
        return True
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
.venv/Scripts/python.exe manage.py test listings.tests.test_backfill_listings
```

Expected: PASS, all 4 tests.

- [ ] **Step 6: Verify pagination live, before relying on this against real brands**

Task 4 flagged that ss.com's pagination past the first page of filtered results was not confirmed during design research. Before running this for real against a brand with more matches than fit on one page: fetch a price-filtered category page live (the browser form-fill approach from design research works for this), check whether a next-page control exists and what it actually submits, and update `ss_client.fetch_filtered_page` and `_backfill_for_search`'s loop accordingly if so. If ss.com returns everything on one page for the brands actually being tracked, note that and move on - don't build pagination handling that has nothing to verify it.

- [ ] **Step 7: Commit**

```bash
git add listings/management/commands/backfill_listings.py listings/tests/fixtures/skoda_filter_results.html listings/tests/test_backfill_listings.py
git commit -m "Add backfill_listings command for existing inventory"
```

---

### Task 7: Display page (filterable car grid)

The user asked specifically for a good-looking display, not a bare template, so this task includes real, complete CSS rather than a placeholder stylesheet: a warm, card-based grid (not a default Bootstrap look), responsive via CSS Grid, with hover states, a stale/probably-sold treatment, and an empty state.

**Files:**
- Create: `listings/views.py`
- Create: `listings/urls.py`
- Create: `listings/templates/listings/car_list.html`
- Create: `listings/static/listings/style.css`
- Modify: `carfinder/urls.py`
- Create: `listings/tests/test_views.py`

**Interfaces:**
- Consumes: `CarListing`, `TrackedSearch` from Task 2.
- Produces: the `car_list` view at `/`, using `CarListing.primary_photo_url` and `CarListing.probably_sold`.

- [ ] **Step 1: Write the failing test**

`listings/tests/test_views.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
.venv/Scripts/python.exe manage.py test listings.tests.test_views
```

Expected: FAIL (no `car_list` URL name yet).

- [ ] **Step 3: Write the view and URLs**

`listings/views.py`:

```python
from django.shortcuts import render

from .models import CarListing, TrackedSearch

ALLOWED_SORTS = {'-first_seen_at', 'price_eur', '-price_eur', 'year', '-year', 'mileage_km'}


def car_list(request):
    listings = CarListing.objects.filter(listing_type=CarListing.FOR_SALE)

    make = request.GET.get('make')
    if make:
        listings = listings.filter(make=make)

    price_min = request.GET.get('price_min')
    if price_min:
        listings = listings.filter(price_eur__gte=price_min)

    price_max = request.GET.get('price_max')
    if price_max:
        listings = listings.filter(price_eur__lte=price_max)

    year_min = request.GET.get('year_min')
    if year_min:
        listings = listings.filter(year__gte=year_min)

    year_max = request.GET.get('year_max')
    if year_max:
        listings = listings.filter(year__lte=year_max)

    sort = request.GET.get('sort', '-first_seen_at')
    if sort not in ALLOWED_SORTS:
        sort = '-first_seen_at'
    listings = listings.order_by(sort)

    context = {
        'listings': listings,
        'tracked_searches': TrackedSearch.objects.filter(active=True),
    }
    return render(request, 'listings/car_list.html', context)
```

`listings/urls.py`:

```python
from django.urls import path

from . import views

urlpatterns = [
    path('', views.car_list, name='car_list'),
]
```

In `carfinder/urls.py`:

```python
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('listings.urls')),
]
```

- [ ] **Step 4: Run test to verify it passes**

```bash
.venv/Scripts/python.exe manage.py test listings.tests.test_views
```

Expected: PASS.

- [ ] **Step 5: Write the template**

`listings/templates/listings/car_list.html`:

```html
{% load static %}
<!DOCTYPE html>
<html lang="lv">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Car Finder</title>
    <link rel="stylesheet" href="{% static 'listings/style.css' %}">
</head>
<body>
    <header class="page-header">
        <h1>Car Finder</h1>
        <p class="subtitle">{{ listings|length }} listing{{ listings|length|pluralize }}</p>
    </header>

    <form class="filters" method="get">
        <select name="make" onchange="this.form.submit()">
            <option value="">All makes</option>
            {% for ts in tracked_searches %}
                <option value="{{ ts.make }}" {% if request.GET.make == ts.make %}selected{% endif %}>{{ ts.make }} {{ ts.model }}</option>
            {% endfor %}
        </select>
        <input type="number" name="price_min" placeholder="Min EUR" value="{{ request.GET.price_min }}">
        <input type="number" name="price_max" placeholder="Max EUR" value="{{ request.GET.price_max }}">
        <input type="number" name="year_min" placeholder="Min year" value="{{ request.GET.year_min }}">
        <input type="number" name="year_max" placeholder="Max year" value="{{ request.GET.year_max }}">
        <select name="sort" onchange="this.form.submit()">
            <option value="-first_seen_at" {% if request.GET.sort == '-first_seen_at' %}selected{% endif %}>Newest found</option>
            <option value="price_eur" {% if request.GET.sort == 'price_eur' %}selected{% endif %}>Price: low to high</option>
            <option value="-price_eur" {% if request.GET.sort == '-price_eur' %}selected{% endif %}>Price: high to low</option>
            <option value="-year" {% if request.GET.sort == '-year' %}selected{% endif %}>Newest year</option>
            <option value="mileage_km" {% if request.GET.sort == 'mileage_km' %}selected{% endif %}>Lowest mileage</option>
        </select>
        <button type="submit">Filter</button>
    </form>

    {% if listings %}
    <div class="car-grid">
        {% for car in listings %}
        <a class="car-card{% if car.probably_sold %} car-card--stale{% endif %}" href="{{ car.listing_url }}" target="_blank" rel="noopener">
            <div class="car-card__photo">
                {% if car.primary_photo_url %}
                    <img src="{{ car.primary_photo_url }}" alt="{{ car.make }} {{ car.model }}" loading="lazy">
                {% else %}
                    <div class="car-card__no-photo">No photo</div>
                {% endif %}
                {% if car.probably_sold %}<span class="car-card__badge">Probably sold</span>{% endif %}
            </div>
            <div class="car-card__body">
                <h2 class="car-card__title">{{ car.make }} {{ car.model }}{% if car.year %} &middot; {{ car.year }}{% endif %}</h2>
                <p class="car-card__price">{% if car.price_eur %}€{{ car.price_eur }}{% else %}Price on request{% endif %}</p>
                <ul class="car-card__specs">
                    {% if car.mileage_km %}<li>{{ car.mileage_km }} km</li>{% endif %}
                    {% if car.engine %}<li>{{ car.engine }}</li>{% endif %}
                    {% if car.transmission %}<li>{{ car.transmission }}</li>{% endif %}
                    {% if car.body_type %}<li>{{ car.body_type }}</li>{% endif %}
                    {% if car.color %}<li>{{ car.color }}</li>{% endif %}
                </ul>
            </div>
        </a>
        {% endfor %}
    </div>
    {% else %}
    <div class="empty-state">
        <p>No listings yet.</p>
        <p>Add a tracked make/model in the <a href="/admin/listings/trackedsearch/">admin</a>, then run <code>fetch_listings</code>.</p>
    </div>
    {% endif %}
</body>
</html>
```

- [ ] **Step 6: Write the stylesheet**

`listings/static/listings/style.css`:

```css
:root {
    --bg: #f6f5f1;
    --surface: #ffffff;
    --text: #1c1b19;
    --text-muted: #6b6862;
    --accent: #b3502b;
    --accent-soft: #f1e4dc;
    --border: #e5e2da;
    --radius: 10px;
}

* {
    box-sizing: border-box;
}

body {
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    line-height: 1.5;
}

.page-header {
    padding: 2.5rem 2rem 1rem;
    max-width: 1200px;
    margin: 0 auto;
}

.page-header h1 {
    margin: 0;
    font-size: 1.75rem;
    letter-spacing: -0.02em;
}

.subtitle {
    color: var(--text-muted);
    margin: 0.25rem 0 0;
    font-size: 0.9rem;
}

.filters {
    max-width: 1200px;
    margin: 0 auto;
    padding: 0 2rem 1.5rem;
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem;
}

.filters select,
.filters input {
    padding: 0.5rem 0.75rem;
    border: 1px solid var(--border);
    border-radius: 6px;
    background: var(--surface);
    color: var(--text);
    font-size: 0.9rem;
}

.filters input[type="number"] {
    width: 7rem;
}

.filters button {
    padding: 0.5rem 1.25rem;
    border: none;
    border-radius: 6px;
    background: var(--accent);
    color: #fff;
    font-size: 0.9rem;
    cursor: pointer;
}

.filters button:hover {
    opacity: 0.9;
}

.car-grid {
    max-width: 1200px;
    margin: 0 auto;
    padding: 0 2rem 3rem;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
    gap: 1.25rem;
}

.car-card {
    display: block;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    overflow: hidden;
    text-decoration: none;
    color: inherit;
    transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.car-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
}

.car-card__photo {
    position: relative;
    aspect-ratio: 4 / 3;
    background: var(--accent-soft);
}

.car-card__photo img {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
}

.car-card__no-photo {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: var(--text-muted);
    font-size: 0.85rem;
}

.car-card__badge {
    position: absolute;
    top: 0.6rem;
    left: 0.6rem;
    background: rgba(28, 27, 25, 0.85);
    color: #fff;
    font-size: 0.7rem;
    padding: 0.2rem 0.5rem;
    border-radius: 4px;
}

.car-card--stale .car-card__photo img {
    filter: grayscale(60%);
    opacity: 0.7;
}

.car-card__body {
    padding: 0.9rem 1rem 1.1rem;
}

.car-card__title {
    margin: 0 0 0.3rem;
    font-size: 1rem;
    font-weight: 600;
    text-transform: capitalize;
}

.car-card__price {
    margin: 0 0 0.6rem;
    font-size: 1.25rem;
    font-weight: 700;
    color: var(--accent);
}

.car-card__specs {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    font-size: 0.78rem;
    color: var(--text-muted);
}

.car-card__specs li {
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 999px;
    padding: 0.15rem 0.6rem;
}

.empty-state {
    max-width: 1200px;
    margin: 0 auto;
    padding: 3rem 2rem;
    text-align: center;
    color: var(--text-muted);
}

.empty-state a {
    color: var(--accent);
}
```

- [ ] **Step 7: Visually verify in the browser**

Add a `car-finder` config to `.claude/launch.json` (runtimeExecutable `.venv/Scripts/python.exe`, args `["manage.py", "runserver"]`, port 8000), start it via `preview_start`, navigate to `/`, and screenshot both the empty state (no listings yet) and, after Task 9 seeds real data, the populated grid.

- [ ] **Step 8: Commit**

```bash
git add listings/views.py listings/urls.py listings/templates listings/static carfinder/urls.py listings/tests/test_views.py
git commit -m "Add filterable car listing display page"
```

---

### Task 8: Scheduled fetching on Windows

Registering a Windows Scheduled Task is a persistent, system-level change that outlives this session, so it should not be run without confirming it with the user first, unlike the rest of this plan's steps.

**Files:**
- Create: `scripts/run_fetch.ps1`
- Create: `README.md` (setup instructions, including the manual registration command)

**Interfaces:**
- Consumes: the `fetch_listings` command from Task 5.

- [ ] **Step 1: Write the wrapper script**

`scripts/run_fetch.ps1`:

```powershell
$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\.."
& ".venv\Scripts\python.exe" manage.py fetch_listings
```

- [ ] **Step 2: Document setup, including the scheduling command**

`README.md`:

```markdown
# Car Finder

Tracks chosen car makes/models on ss.com and displays matches.

## Setup

    python -m venv .venv
    .venv/Scripts/python.exe -m pip install -r requirements.txt
    .venv/Scripts/python.exe manage.py migrate
    .venv/Scripts/python.exe manage.py createsuperuser

Add tracked makes/models at /admin/listings/trackedsearch/, then run:

    .venv/Scripts/python.exe manage.py fetch_listings

## Automatic fetching

To fetch every 20 minutes, register a Windows Scheduled Task:

    schtasks /create /tn "CarFinderFetch" /tr "powershell.exe -ExecutionPolicy Bypass -File \"<repo-path>\scripts\run_fetch.ps1\"" /sc minute /mo 20 /f

Replace `<repo-path>` with the full path to this repo. Remove it later with:

    schtasks /delete /tn "CarFinderFetch" /f
```

- [ ] **Step 3: Confirm with the user, then register the task**

Ask the user before running the `schtasks /create` command above (substituting the real repo path) - this installs a background task that persists across reboots. If they agree, run it and verify with `schtasks /query /tn "CarFinderFetch"`.

- [ ] **Step 4: Commit**

```bash
git add scripts/run_fetch.ps1 README.md
git commit -m "Document and script scheduled fetching"
```

---

### Task 9: Seed real tracked search and verify end-to-end

**Files:** none created; this exercises everything built so far against the live site, seeded with the tracked searches actually wanted: Volkswagen, Skoda, Audi and Honda, each brand-wide, capped at 1200 EUR, requiring valid TA.

- [ ] **Step 1: Add the real tracked searches**

Via `/admin/listings/trackedsearch/add/` in the browser (or `manage.py shell`), create four `TrackedSearch` rows, each with `model=''`, `max_price_eur=1200`, `require_ta=True`, `active=True`: `make='volkswagen'`, `make='skoda'`, `make='audi'`, `make='honda'`.

- [ ] **Step 2: Run the fetch command against the real site**

```bash
.venv/Scripts/python.exe manage.py fetch_listings
```

Expected output: four success lines, one per brand, each showing some number seen and new (exact counts vary with live inventory - VW and Skoda are high-traffic, expect this to take a while and make real requests for every match under the price ceiling).

- [ ] **Step 3: Run the backfill command to pick up what's already listed**

```bash
.venv/Scripts/python.exe manage.py backfill_listings
```

Expected output: four more lines, new counts likely higher than Step 2's since this covers current inventory, not just recent activity. Re-running it should show 0 new for anything Step 2 or a prior backfill run already found - confirm this by running it a second time.

- [ ] **Step 4: Confirm the data landed correctly and respects the requirements**

```bash
.venv/Scripts/python.exe manage.py shell -c "from listings.models import CarListing; print(CarListing.objects.filter(listing_type='for_sale').count()); print(CarListing.objects.filter(listing_type='for_sale', price_eur__gt=1200).count()); print(CarListing.objects.filter(listing_type='for_sale').exclude(ta_valid_until__isnull=False).count())"
```

Expected: some number of for-sale listings, and the second and third numbers both 0 - nothing over the price ceiling, nothing without a TA date, since both are meant to be excluded before a row is ever created.

- [ ] **Step 5: Look at the actual page, not just the data**

Start the dev server via `preview_start`, open `/`, and using the Browser pane: confirm photos load, prices and specs display correctly, all four makes appear, no listing shows a price over 1200 EUR, and the "probably sold" styling is not incorrectly applied to fresh listings. Try the make/price/year filters and the sort dropdown. Screenshot the result.

- [ ] **Step 6: Run the full test suite one more time**

```bash
.venv/Scripts/python.exe manage.py test
```

Expected: all tests pass.

- [ ] **Step 7: Commit any fixture/config adjustments made during verification**

```bash
git add -A
git commit -m "Verify end-to-end fetch and backfill against live ss.com data"
```
