from django.contrib import admin
from django.utils.html import format_html
from simple_history.admin import SimpleHistoryAdmin

from .models import LedgerEntry, IncomeEntry


@admin.register(LedgerEntry)
class LedgerEntryAdmin(SimpleHistoryAdmin):
    list_display = (
        'uhid', 'patient_link', 'tx_type', 'payer_type',
        'debit_display', 'credit_display',
        'payment_mode', 'source_app', 'claim_no', 'claim_status', 'created_at',
    )
    list_filter  = ('payer_type', 'tx_type', 'claim_status', 'source_app', 'payment_mode')
    search_fields = ('uhid', 'claim_no', 'description',
                     'tpa_name', 'insurance_company', 'policy_no',
                     'patient__name', 'patient__uhid')
    readonly_fields  = ('created_at', 'created_by')
    date_hierarchy   = 'created_at'
    list_per_page    = 40
    list_select_related = ('patient', 'created_by')
    ordering         = ('-created_at',)

    # Ledger rows are financial/legal records — prevent direct editing.
    # Corrections must be done via new adjustment rows.
    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def debit_display(self, obj):
        if obj.debit_amount:
            return format_html(
                '<span style="color:#991b1b;font-family:monospace;font-weight:600">'
                '▲ ₹ {:,.2f}</span>', obj.debit_amount
            )
        return '—'
    debit_display.short_description = 'Debit (DR)'
    debit_display.admin_order_field = 'debit_amount'

    def credit_display(self, obj):
        if obj.credit_amount:
            return format_html(
                '<span style="color:#065f46;font-family:monospace;font-weight:600">'
                '▼ ₹ {:,.2f}</span>', obj.credit_amount
            )
        return '—'
    credit_display.short_description = 'Credit (CR)'
    credit_display.admin_order_field = 'credit_amount'

    def patient_link(self, obj):
        if obj.patient:
            return format_html(
                '<a href="/admin/uhid/patient/{}/change/" style="font-size:12px">{}</a>',
                obj.patient.pk, obj.patient.name,
            )
        return format_html('<span style="color:#aaa;font-size:11px">{}</span>', obj.uhid)
    patient_link.short_description = 'Patient'


@admin.register(IncomeEntry)
class IncomeEntryAdmin(SimpleHistoryAdmin):
    list_display  = ('date', 'category_badge', 'patient_name',
                     'description_preview', 'amount_display', 'payment_mode_badge', 'created_at')
    list_filter   = ('category', 'payment_mode', 'date')
    search_fields = ('patient_name', 'description')
    readonly_fields = ('created_at',)
    date_hierarchy  = 'date'
    list_per_page   = 40
    ordering        = ('-date', '-created_at')

    def amount_display(self, obj):
        return format_html(
            '<span style="font-family:monospace;font-weight:600">₹ {:,.2f}</span>',
            obj.amount,
        )
    amount_display.short_description = 'Amount'
    amount_display.admin_order_field = 'amount'

    def category_badge(self, obj):
        colours = {
            'OPD':          ('#1d4ed8', '#dbeafe'),
            'IPD':          ('#065f46', '#d1fae5'),
            'Investigation':('#5b21b6', '#ede9fe'),
            'Pharmacy':     ('#0e7490', '#cffafe'),
            'Ultrasound':   ('#c2410c', '#ffedd5'),
            'OT':           ('#6b21a8', '#f3e8ff'),
            'Extra':        ('#374151', '#f1f5f9'),
        }
        fg, bg = colours.get(obj.category, ('#374151', '#f1f5f9'))
        return format_html(
            '<span style="background:{};color:{};padding:2px 9px;'
            'border-radius:12px;font-size:11px">{}</span>',
            bg, fg, obj.category,
        )
    category_badge.short_description = 'Category'

    def payment_mode_badge(self, obj):
        colours = {
            'Cash':   ('#065f46', '#d1fae5'),
            'UPI':    ('#1d4ed8', '#dbeafe'),
            'Card':   ('#5b21b6', '#ede9fe'),
            'Cheque': ('#78350f', '#fef3c7'),
        }
        fg, bg = colours.get(obj.payment_mode, ('#374151', '#f1f5f9'))
        return format_html(
            '<span style="background:{};color:{};padding:2px 9px;'
            'border-radius:12px;font-size:11px">{}</span>',
            bg, fg, obj.payment_mode,
        )
    payment_mode_badge.short_description = 'Mode'

    def description_preview(self, obj):
        short = str(obj.description)[:50] + ('…' if len(str(obj.description)) > 50 else '')
        return format_html('<span style="font-size:12px;color:#555">{}</span>', short)
    description_preview.short_description = 'Description'
