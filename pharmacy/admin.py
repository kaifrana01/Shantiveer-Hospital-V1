from django.contrib import admin
from django.utils.html import format_html
from simple_history.admin import SimpleHistoryAdmin

from .models import PharmacyItem, PharmacyPurchase, PharmacySale


@admin.register(PharmacyItem)
class PharmacyItemAdmin(SimpleHistoryAdmin):
    list_display  = ('name', 'drug', 'unit_type', 'stock_badge', 'sale_price',
                     'buffer', 'schedule', 'status_badge')
    list_filter   = ('is_active', 'unit_type', 'schedule')
    search_fields = ('name', 'drug', 'hsn')
    ordering      = ('name',)
    list_per_page = 40

    fieldsets = (
        ('Item Details',   {'fields': ('name', 'drug', 'unit_type', 'packing', 'hsn', 'schedule')}),
        ('Stock & Pricing',{'fields': ('stock', 'buffer', 'sale_price', 'discount_on_sale')}),
        ('Status',         {'fields': ('is_active',)}),
    )

    def stock_badge(self, obj):
        if obj.stock == 0:
            return format_html(
                '<span style="background:#fee2e2;color:#991b1b;padding:2px 8px;'
                'border-radius:12px;font-size:11px;font-weight:600">Out of Stock</span>'
            )
        if obj.stock <= obj.buffer:
            return format_html(
                '<span style="background:#fef3c7;color:#78350f;padding:2px 8px;'
                'border-radius:12px;font-size:11px;font-weight:600">Low: {}</span>',
                obj.stock,
            )
        return format_html(
            '<span style="background:#d1fae5;color:#065f46;padding:2px 8px;'
            'border-radius:12px;font-size:11px">{}</span>',
            obj.stock,
        )
    stock_badge.short_description = 'Stock'
    stock_badge.admin_order_field = 'stock'

    def status_badge(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="background:#d1fae5;color:#065f46;padding:2px 8px;'
                'border-radius:12px;font-size:11px">● Active</span>'
            )
        return format_html(
            '<span style="background:#fee2e2;color:#991b1b;padding:2px 8px;'
            'border-radius:12px;font-size:11px">● Inactive</span>'
        )
    status_badge.short_description = 'Status'


@admin.register(PharmacyPurchase)
class PharmacyPurchaseAdmin(SimpleHistoryAdmin):
    list_display  = ('item', 'supplier', 'quantity', 'rate', 'total_value', 'purchased_at')
    list_filter   = ('purchased_at',)
    search_fields = ('item__name', 'supplier')
    ordering      = ('-purchased_at',)
    readonly_fields = ('purchased_at',)
    list_per_page = 40

    def total_value(self, obj):
        return format_html(
            '<span style="font-family:monospace">₹ {:,.2f}</span>',
            obj.quantity * obj.rate,
        )
    total_value.short_description = 'Total Value'


@admin.register(PharmacySale)
class PharmacySaleAdmin(SimpleHistoryAdmin):
    list_display  = ('item', 'patient_ref', 'quantity', 'amount_display',
                     'payment_mode', 'sold_at')
    list_filter   = ('payment_mode', 'sold_at')
    search_fields = ('item__name', 'patient_ref')
    readonly_fields = ('sold_at',)
    ordering      = ('-sold_at',)
    list_per_page = 40

    def amount_display(self, obj):
        return format_html(
            '<span style="font-family:monospace">₹ {:,.2f}</span>', obj.amount
        )
    amount_display.short_description = 'Amount'
    amount_display.admin_order_field = 'amount'
