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
