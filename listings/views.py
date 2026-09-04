from django.shortcuts import render

from .models import TrackedSearch
from .queries import for_sale_listings

ALLOWED_SORTS = {'-first_seen_at', 'price_eur', '-price_eur', 'year', '-year', 'mileage_km'}


def car_list(request):
    listings = for_sale_listings(make=request.GET.get('make'), period=request.GET.get('period'))

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
