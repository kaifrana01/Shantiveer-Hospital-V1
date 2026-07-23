from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin
from .models import PharmacyItem, PharmacyPurchase, PharmacySale


@admin.register(PharmacySale)
class PharmacySaleAdmin(SimpleHistoryAdmin):
    list_display = ('item', 'patient_ref', 'quantity', 'amount', 'payment_mode', 'sold_at')
    search_fields = ('item__name', 'patient_ref')
    list_filter = ('payment_mode',)


admin.site.register(PharmacyItem)
admin.site.register(PharmacyPurchase)
