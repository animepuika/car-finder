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
    engine = models.CharField(max_length=50, null=True, blank=True)
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
