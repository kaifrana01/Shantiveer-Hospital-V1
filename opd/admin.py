from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin
from .models import OPDVisit


@admin.register(OPDVisit)
class OPDVisitAdmin(SimpleHistoryAdmin):
    list_display = ('opd_no', 'patient', 'date', 'doctor_name', 'total_amount', 'payment_mode')
    search_fields = ('opd_no', 'patient__name', 'patient__uhid', 'doctor_name')
    list_filter = ('payment_mode',)
