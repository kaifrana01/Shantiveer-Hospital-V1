from django.contrib import admin
from django.utils.html import format_html
from .models import Doctor, TestInterpretation


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ('name', 'department', 'specialization', 'phone', 'status_badge')
    list_filter = ('is_active', 'department')
    search_fields = ('name', 'department', 'specialization', 'phone')
    list_per_page = 25
    ordering = ('name',)

    fieldsets = (
        ('Doctor Details', {'fields': ('name', 'department', 'specialization', 'phone', 'is_active')}),
    )

    def status_badge(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="background:#d1fae5;color:#065f46;padding:2px 10px;border-radius:12px;font-size:11px">● Active</span>'
            )
        return format_html(
            '<span style="background:#fee2e2;color:#991b1b;padding:2px 10px;border-radius:12px;font-size:11px">● Inactive</span>'
        )
    status_badge.short_description = 'Status'


@admin.register(TestInterpretation)
class TestInterpretationAdmin(admin.ModelAdmin):
    list_display = ('test_name', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('test_name',)
    ordering = ('test_name',)
