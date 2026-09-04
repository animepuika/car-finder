# Car Finder - Design Spec

## Purpose

A personal tool that automatically tracks specific car makes/models on ss.com
(Latvia's largest classifieds site) and displays matching listings, photos,
specs, price, on a single website, so cars don't need to be hunted down
manually one listing at a time.

Single user (just the owner). No accounts, no public submissions.

## Data source: ss.com

ss.com publishes a live RSS feed per make/model category (e.g.
`ss.com/lv/transport/cars/volkswagen/golf-3/rss/`), confirmed during design
research:

- robots.txt permits crawling listing and category pages (only blocks
  utility/duplicate-content paths like city-filtered views and contact forms)
- No login required to browse
- Terms of service reviewed; no clause found prohibiting automated access
  (not a legal guarantee, but no red flag either)
- The existence of a per-category RSS feed indicates the site is built for
  this kind of automated consumption, unlike a platform such as Facebook
  Marketplace that requires login and actively blocks automated access

RSS gives: make, model, year, engine, mileage, price, one thumbnail, listing
URL. It does not give: transmission, body type, color, full photo gallery,
description - those require fetching the individual listing page, which is
equally public and not blocked by robots.txt.

RSS feeds also exist one level up, per brand rather than per model (e.g.
`ss.com/lv/transport/cars/volkswagen/rss/`, confirmed live), mixing every
model of that brand together. Brand-level items include a `Modelis` field
identifying which model each one is, since it isn't implied by the URL the
way it is for a model-specific feed.

Only ss.com for v1. Other Latvian sites (automoto.com.lv, autopase.lv, etc.)
are not vetted and are out of scope until each is checked the same way.

### Backfill: listings that already exist, not just new ones

RSS only shows a rolling window of the most recent items - fine for a narrow,
low-volume model, but it will not surface the full existing inventory for a
whole brand. ss.com's category pages have a real price-filter form (confirmed
live, not guessed) that POSTs to `/lv/transport/cars/{make}/filter/` with
fields `topt[8][min]` and `topt[8][max]`, and returns the actual current
matching inventory, not just recent activity. A one-time (re-runnable)
backfill against this endpoint, in addition to ongoing RSS polling, covers
both "what's new" and "what's already listed."

Only the verified mechanisms (RSS, this real form) are used. The category
page also contains at least one honeypot link matching robots.txt's
disallowed obfuscated pattern (`/fDgSeF4*.html`) - confirmation that ss.com's
anti-bot measures are real, and a reason to never follow a link that wasn't
explicitly confirmed as one of the two mechanisms above.

## Architecture

Django + SQLite, matching the stack already known from the HiFinder project:

- A scheduled management command (`fetch_listings`) does the polling,
  triggered by Windows Task Scheduler every 20-30 minutes.
- SQLite for storage (single user, modest data volume, no need for anything
  heavier).
- Django admin for managing tracked searches (add "Golf 3" without touching
  code).
- Server-rendered templates for the display/browse page.

## Data model

**TrackedSearch**
- `make` (str, e.g. "volkswagen") - matches ss.com's URL slug
- `model` (str, optional) - matches ss.com's URL slug; blank means track the
  whole brand (every model), not one specific model
- `max_price_eur` (int, optional) - a price ceiling for this tracked search.
  When set, this is a fetch-time exclusion, not a display filter: at
  brand-wide scale (thousands of listings per brand) there is no reason to
  fetch a detail page or store a row for something that will never be shown
  because it is already known from RSS to be over budget
- `require_ta` (bool, default False) - when true, only listings with a
  currently-valid technical inspection (see `ta_valid_until` below) are kept.
  Also a fetch-time exclusion, for the same reason as price
- `active` (bool)

Year/mileage still filter at display time (cheap, and the point of them is
ad-hoc narrowing while browsing, not reducing what gets fetched). Price and
TA are different: they are hard requirements set once when configuring what
to track, so filtering them out before saving keeps the database from
filling up with rows that were never going to be shown, and avoids
detail-page requests for listings already excluded by price alone.

**CarListing**
- `listing_url` (unique, the dedup key)
- `tracked_search` (FK)
- `make`, `model`, `year`, `engine`, `transmission`, `body_type`, `color`
- `mileage_km`, `price_eur` (nullable, "wanted" posts have no price)
- `listing_type` (`for_sale` / `wanted`) - ss.com's feeds mix in "buying"
  posts (price shown as the literal text "perku") alongside actual for-sale
  listings; these must not be displayed as if they were cars you can buy
- `ta_valid_until` (date, nullable) - parsed from the listing's "Tehniskā
  apskate" field on the detail page (the same specs table already being
  read; no new page structure involved). Null means no TA date was found on
  the listing at all
- `thumbnail_url`, `photo_urls` (list)
- `description` (text)
- `first_seen_at`, `last_seen_at` (datetime)

## Fetch flow

Two mechanisms, both per active `TrackedSearch`:

**Ongoing discovery (RSS, scheduled every 20-30 min):**

1. Fetch the RSS feed - model-specific if `model` is set, brand-wide
   (`/lv/transport/cars/{make}/rss/`) otherwise.
2. For each item: if `max_price_eur` is set and the price RSS already gives
   is over it, skip entirely - no detail-page request, nothing saved.
3. Otherwise, if `listing_url` is new, fetch the individual listing page for
   full spec details (including TA). If `require_ta` is set and the listing
   has no currently-valid TA, skip - don't save it. Otherwise create the
   `CarListing`.
4. If already known, update `last_seen_at` and price (in case it changed).
5. A listing not refreshed in 14+ days is treated as probably sold and shown
   as such in the UI, rather than re-verified with an extra request. This is
   a cheap heuristic, good enough for a personal tool.

**Backfill (one-time or re-run on demand, not on the schedule):**

For a `TrackedSearch` with `max_price_eur` set, POST that price ceiling to
ss.com's real filter endpoint and walk the results, applying the same
new/exclude/enrich logic as step 2-3 above to each one. This is what actually
satisfies "cars that are already there," since RSS alone would only catch
whatever happened to still be in its recent window at the moment of the
first fetch.

## Error handling

- Each `TrackedSearch` is processed independently. One failing (network
  error, site hiccup) doesn't stop the others.
- If the detail-page fetch fails after the RSS item was found, the
  `CarListing` is still created from what RSS provided rather than dropped
  entirely.
- A short delay between detail-page requests avoids bursting the site with
  requests.

## Testing

Django tests run against saved fixture RSS/HTML, not live requests:

- RSS parsing produces the expected fields
- Running the fetch twice doesn't create duplicates
- "Wanted" posts are excluded from for-sale display

## Explicitly out of scope for v1

- Other data sources beyond ss.com
- Price history over time (only current price is kept)
- Notifications/alerts (email, push); the display page itself is the only
  surface
- Fetch-time filtering by year/mileage (handled at display time instead;
  price and TA are the exception - see Data model)
- Active re-verification of "probably sold" listings
- Multi-user accounts, public access

## Project location

New repo at `~/Desktop/car-finder`, separate from HiFinder.
