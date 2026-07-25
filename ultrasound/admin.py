from django.contrib import admin
from django.utils.html import format_html
from simple_history.admin import SimpleHistoryAdmin

from .models import (
    UltrasoundTestMaster,
    UltrasoundInvestigation,
    UltrasoundInvestigationItem,
    UltrasoundDocument,
    UltrasoundExpense,
)


@admin.register(UltrasoundTestMaster)
class UltrasoundTestMasterAdmin(SimpleHistoryAdmin):
    list_display  = ('name', 'rate_display', 'status_badge')
    list_filter   = ('is_active',)
    search_fields = ('name',)
    ordering      = ('name',)
    list_per_page = 40

    def rate_display(self, obj):
        return format_html(
            '<span style="font-family:monospace">₹ {:,.2f}</span>', obj.rate
        )
    rate_display.short_description = 'Rate'
    rate_display.admin_order_field = 'rate'

    def status_badge(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="background:#d1fae5;color:#065f46;padding:2px 9px;'
                'border-radius:12px;font-size:11px">● Active</span>'
            )
        return format_html(
            '<span style="background:#fee2e2;color:#991b1b;padding:2px 9px;'
            'border-radius:12px;font-size:11px">● Inactive</span>'
        )
    status_badge.short_description = 'Status'


class UltrasoundItemInline(admin.TabularInline):
    model   = UltrasoundInvestigationItem
    extra   = 0
    fields  = ('test', 'rate', 'quantity', 'amount')
    readonly_fields = ('amount',)


class UltrasoundDocumentInline(admin.TabularInline):
    model   = UltrasoundDocument
    extra   = 0
    fields  = ('file', 'uploaded_at')
    readonly_fields = ('uploaded_at',)


@admin.register(UltrasoundInvestigation)
class UltrasoundInvestigationAdmin(SimpleHistoryAdmin):
    list_display  = ('bill_no', 'patient_name', 'mobile', 'consultant',
                     'total_display', 'discount', 'payment_mode', 'test_date')
    list_filter   = ('payment_mode', 'test_date', 'gender')
    search_fields = ('bill_no', 'patient_name', 'mobile', 'consultant', 'referred_by')
    date_hierarchy = 'test_date'
    readonly_fields = ('bill_no', 'created_at')
    inlines       = [UltrasoundItemInline, UltrasoundDocumentInline]
    list_per_page = 30
    ordering      = ('-test_date', '-created_at')

    fieldsets = (
        ('Bill',    {'fields': ('bill_no', 'test_date', 'payment_mode', 'discount', 'total')}),
        ('Patient', {'fields': ('patient', 'patient_name', 'age', 'gender', 'mobile', 'address')}),
        ('Clinical',{'fields': ('consultant', 'referred_by', 'remarks')}),
        ('Meta',    {'fields': ('created_at',), 'classes': ('collapse',)}),
    )

    def total_display(self, obj):
        return format_html(
            '<span style="font-family:monospace;font-weight:600">₹ {:,.2f}</span>',
            obj.total,
        )
    total_display.short_description = 'Total'
    total_display.admin_order_field = 'total'


@admin.register(UltrasoundExpense)
class UltrasoundExpenseAdmin(admin.ModelAdmin):
    list_display  = ('date', 'category', 'description', 'amount_display', 'remarks')
    list_filter   = ('category', 'date')
    search_fields = ('description', 'remarks')
    ordering      = ('-date', '-created_at')
    readonly_fields = ('created_at',)
    list_per_page = 40

    def amount_display(self, obj):
        return format_html(
            '<span style="font-family:monospace">₹ {:,.2f}</span>', obj.amount
        )
    amount_display.short_description = 'Amount'
    amount_display.admin_order_field = 'amount'
