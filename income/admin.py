from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin
from .models import LedgerEntry, IncomeEntry


@admin.register(LedgerEntry)
class LedgerEntryAdmin(SimpleHistoryAdmin):
    list_display = (
        'uhid', 'tx_type', 'payer_type', 'debit_amount', 'credit_amount',
        'claim_no', 'claim_status', 'source_app', 'created_at',
    )
    list_filter = ('payer_type', 'tx_type', 'claim_status', 'source_app', 'payment_mode')
    search_fields = ('uhid', 'claim_no', 'description', 'tpa_name', 'insurance_company', 'policy_no')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'


@admin.register(IncomeEntry)
class IncomeEntryAdmin(SimpleHistoryAdmin):
    list_display = ('date', 'category', 'patient_name', 'amount', 'payment_mode')
    list_filter = ('category', 'payment_mode')
    search_fields = ('patient_name', 'description')
