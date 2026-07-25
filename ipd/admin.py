from django.contrib import admin
from django.utils.html import format_html
from simple_history.admin import SimpleHistoryAdmin

from .models import IPDAdmission, IPDPayment, IPDMedicineLine, DischargeSummary


class IPDPaymentInline(admin.TabularInline):
    model   = IPDPayment
    extra   = 0
    fields  = ('amount', 'payment_mode', 'upi_id', 'remarks', 'paid_at')
    readonly_fields = ('paid_at',)


class IPDMedicineInline(admin.TabularInline):
    model  = IPDMedicineLine
    extra  = 0
    fields = ('medicine_name', 'quantity', 'rate', 'amount')
    readonly_fields = ('amount',)


@admin.register(IPDAdmission)
class IPDAdmissionAdmin(SimpleHistoryAdmin):
    list_display  = ('ipd_no', 'patient_link', 'date', 'category_badge',
                     'room_no', 'consultant', 'status_badge', 'tpa', 'insurance_co')
    list_filter   = ('status', 'category', 'date')
    search_fields = ('ipd_no', 'patient__name', 'patient__uhid',
                     'policy_no', 'tpa', 'insurance_co', 'consultant')
    readonly_fields = ('ipd_no', 'created_at')
    date_hierarchy = 'date'
    inlines       = [IPDPaymentInline, IPDMedicineInline]
    list_per_page = 30
    ordering      = ('-date',)

    fieldsets = (
        ('Patient',    {'fields': ('ipd_no', 'patient', 'date', 'time', 'status')}),
        ('Ward',       {'fields': ('category', 'room_category', 'room_no', 'bed_charge')}),
        ('Clinical',   {'fields': ('consultant', 'diagnosis', 'guardian', 'referral')}),
        ('KYC',        {'fields': ('kyc_type', 'kyc_no')}),
        ('Insurance',  {'fields': ('tpa', 'policy_no', 'insurance_co')}),
        ('Timestamps', {'fields': ('created_at',), 'classes': ('collapse',)}),
    )

    def patient_link(self, obj):
        return format_html(
            '<a href="/admin/uhid/patient/{}/change/" style="font-size:12px">'
            '{} ({})</a>',
            obj.patient.pk, obj.patient.name, obj.patient.uhid,
        )
    patient_link.short_description = 'Patient'

    def status_badge(self, obj):
        if obj.status == 'Admitted':
            return format_html(
                '<span style="background:#d1fae5;color:#065f46;padding:2px 9px;'
                'border-radius:12px;font-size:11px;font-weight:600">● Admitted</span>'
            )
        return format_html(
            '<span style="background:#e5e7eb;color:#374151;padding:2px 9px;'
            'border-radius:12px;font-size:11px">Discharged</span>'
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'

    def category_badge(self, obj):
        colours = {
            'ICU':           ('#991b1b', '#fee2e2'),
            'Private Ward':  ('#1d4ed8', '#dbeafe'),
            'General Ward':  ('#065f46', '#d1fae5'),
        }
        fg, bg = colours.get(obj.category, ('#374151', '#f1f5f9'))
        return format_html(
            '<span style="background:{};color:{};padding:2px 8px;'
            'border-radius:12px;font-size:11px">{}</span>',
            bg, fg, obj.category,
        )
    category_badge.short_description = 'Category'


@admin.register(IPDPayment)
class IPDPaymentAdmin(SimpleHistoryAdmin):
    list_display  = ('admission', 'amount_display', 'payment_mode', 'upi_id', 'remarks', 'paid_at')
    list_filter   = ('payment_mode', 'paid_at')
    search_fields = ('admission__ipd_no', 'admission__patient__name', 'remarks')
    readonly_fields = ('paid_at',)
    ordering      = ('-paid_at',)
    list_per_page = 40

    def amount_display(self, obj):
        return format_html(
            '<span style="font-family:monospace;font-weight:600">₹ {:,.2f}</span>',
            obj.amount,
        )
    amount_display.short_description = 'Amount'
    amount_display.admin_order_field = 'amount'


@admin.register(IPDMedicineLine)
class IPDMedicineLineAdmin(SimpleHistoryAdmin):
    list_display  = ('admission', 'medicine_name', 'quantity', 'rate', 'amount')
    search_fields = ('admission__ipd_no', 'admission__patient__name', 'medicine_name')
    list_filter   = ()
    list_per_page = 40


@admin.register(DischargeSummary)
class DischargeSummaryAdmin(SimpleHistoryAdmin):
    list_display  = ('admission', 'discharge_date', 'notes_preview')
    search_fields = ('admission__ipd_no', 'admission__patient__name')
    list_filter   = ('discharge_date',)
    list_per_page = 30

    def notes_preview(self, obj):
        if obj.notes:
            short = obj.notes[:80] + ('…' if len(obj.notes) > 80 else '')
            return format_html('<span style="font-size:12px;color:#555">{}</span>', short)
        return format_html('<span style="color:#aaa">—</span>')
    notes_preview.short_description = 'Notes'
