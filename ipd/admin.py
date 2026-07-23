from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin
from .models import IPDAdmission, IPDPayment, IPDMedicineLine, DischargeSummary


@admin.register(IPDAdmission)
class IPDAdmissionAdmin(SimpleHistoryAdmin):
    list_display = ('ipd_no', 'patient', 'date', 'room_no', 'status', 'tpa', 'insurance_co')
    search_fields = ('ipd_no', 'patient__name', 'patient__uhid', 'policy_no', 'tpa')
    list_filter = ('status', 'category')


@admin.register(IPDPayment)
class IPDPaymentAdmin(SimpleHistoryAdmin):
    list_display = ('admission', 'amount', 'payment_mode', 'paid_at')
    search_fields = ('admission__ipd_no', 'admission__patient__name')
    list_filter = ('payment_mode',)


admin.site.register(IPDMedicineLine)
admin.site.register(DischargeSummary)
