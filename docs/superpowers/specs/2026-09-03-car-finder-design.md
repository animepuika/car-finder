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

Only ss.com for v1. Other Latvian sites (automoto.com.lv, autopase.lv, etc.)
are not vetted and are out of scope until each is checked the same way.

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
- `model` (str, e.g. "golf-3") - matches ss.com's URL slug
- `active` (bool)

Filtering by price/year/mileage happens at display time, not here. The
per-model feed is already small enough that pre-filtering the fetch isn't
worth the complexity.

**CarListing**
- `listing_url` (unique, the dedup key)
- `tracked_search` (FK)
- `make`, `model`, `year`, `engine`, `transmission`, `body_type`, `color`
- `mileage_km`, `price_eur` (nullable, "wanted" posts have no price)
- `listing_type` (`for_sale` / `wanted`) - ss.com's feeds mix in "buying"
  posts (price shown as the literal text "perku") alongside actual for-sale
  listings; these must not be displayed as if they were cars you can buy
- `thumbnail_url`, `photo_urls` (list)
- `description` (text)
- `first_seen_at`, `last_seen_at` (datetime)

## Fetch flow

For each active `TrackedSearch`:

1. Fetch its RSS feed.
2. For each item: if `listing_url` is new, fetch the individual listing page
   for full spec details and create a `CarListing`. If already known, update
   `last_seen_at` and price (in case it changed).
3. A listing not refreshed in 14+ days is treated as probably sold and shown
   as such in the UI, rather than re-verified with an extra request. This is
   a cheap heuristic, good enough for a personal tool.

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
- Fetch-time filtering by price/year (handled at display time instead)
- Active re-verification of "probably sold" listings
- Multi-user accounts, public access

## Project location

New repo at `~/Desktop/car-finder`, separate from HiFinder.
