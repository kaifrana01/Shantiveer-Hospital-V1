from django.contrib import admin
from django.utils.html import format_html
from .models import LabTestMaster, LabInvestigation, LabInvestigationItem, LabTestResult
from simple_history.admin import SimpleHistoryAdmin


@admin.register(LabTestMaster)
class LabTestMasterAdmin(SimpleHistoryAdmin):
    list_display = ('name', 'rate_display', 'status_badge', 'history_count')
    list_filter = ('is_active',)
    search_fields = ('name',)
    list_per_page = 30
    ordering = ('name',)

    fieldsets = (
        ('Test Details', {'fields': ('name', 'rate', 'is_active')}),
    )

    def rate_display(self, obj):
        return format_html(
            '<span style="font-family:monospace;font-size:13px">₹ {}</span>',
            '{:,.2f}'.format(obj.rate)
        )
    rate_display.short_description = 'Rate (₹)'
    rate_display.admin_order_field = 'rate'

    def status_badge(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="background:#d1fae5;color:#065f46;padding:2px 10px;'
                'border-radius:12px;font-size:11px">● Active</span>'
            )
        return format_html(
            '<span style="background:#fee2e2;color:#991b1b;padding:2px 10px;'
            'border-radius:12px;font-size:11px">● Inactive</span>'
        )
    status_badge.short_description = 'Status'

    def history_count(self, obj):
        count = obj.history.count()
        return format_html(
            '<span style="background:#ede9fe;color:#4c1d95;padding:2px 8px;'
            'border-radius:12px;font-size:11px"><i class="bi bi-clock-history"></i> {} edit{}</span>',
            count, 's' if count != 1 else ''
        )
    history_count.short_description = 'Revision History'


class LabInvestigationItemInline(admin.TabularInline):
    model = LabInvestigationItem
    extra = 1
    fields = ('test', 'rate', 'quantity', 'amount')
    readonly_fields = ('amount',)


@admin.register(LabInvestigation)
class LabInvestigationAdmin(SimpleHistoryAdmin):
    list_display = (
        'bill_no', 'patient_name', 'consultant_display',
        'total_display', 'payment_mode', 'test_date', 'created_at_display'
    )
    list_filter = ('payment_mode', 'test_date', 'created_at')
    search_fields = ('bill_no', 'patient_name', 'mobile', 'consultant')
    date_hierarchy = 'test_date'
    readonly_fields = ('bill_no', 'created_at')
    inlines = [LabInvestigationItemInline]
    list_per_page = 25

    def consultant_display(self, obj):
        return obj.consultant or '—'
    consultant_display.short_description = 'Consultant'

    def total_display(self, obj):
        return format_html('<span style="font-family:monospace">₹ {:,.2f}</span>', obj.total)
    total_display.short_description = 'Total'

    def created_at_display(self, obj):
        from django.utils import timezone
        local = timezone.localtime(obj.created_at)
        return format_html(
            '<span style="font-size:11px;color:#555">{}</span>',
            local.strftime('%d %b %Y %H:%M')
        )
    created_at_display.short_description = 'Created'
