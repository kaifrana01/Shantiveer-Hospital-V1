from django.contrib import admin
from django.utils.html import format_html
from simple_history.admin import SimpleHistoryAdmin

from .models import Bed, Notification
from .backup_models import BackupSchedule, BackupRecord


@admin.register(Bed)
class BedAdmin(SimpleHistoryAdmin):
    list_display  = ('room_no', 'bed_no', 'status_badge', 'patient_link')
    list_filter   = ('status',)
    search_fields = ('room_no', 'bed_no', 'patient__name', 'patient__uhid')
    ordering      = ('room_no', 'bed_no')
    list_per_page = 50

    def status_badge(self, obj):
        colours = {
            'Occupied':    ('#991b1b', '#fee2e2'),
            'Vacant':      ('#065f46', '#d1fae5'),
            'Maintenance': ('#78350f', '#fef3c7'),
        }
        fg, bg = colours.get(obj.status, ('#374151', '#f1f5f9'))
        return format_html(
            '<span style="background:{};color:{};padding:2px 10px;'
            'border-radius:12px;font-size:11px;font-weight:600">● {}</span>',
            bg, fg, obj.status,
        )
    status_badge.short_description = 'Status'
    status_badge.admin_order_field = 'status'

    def patient_link(self, obj):
        if obj.patient:
            return format_html(
                '<a href="/uhid/?q={}" style="font-size:12px">{} ({})</a>',
                obj.patient.uhid, obj.patient.name, obj.patient.uhid,
            )
        return format_html('<span style="color:#aaa;font-size:12px">—</span>')
    patient_link.short_description = 'Patient'


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display  = ('title', 'notification_type', 'user', 'is_read', 'created_at')
    list_filter   = ('notification_type', 'is_read', 'created_at')
    search_fields = ('title', 'message', 'user__username')
    readonly_fields = ('created_at',)
    ordering      = ('-created_at',)
    list_per_page = 40

    def has_add_permission(self, request):
        return False  # notifications are system-generated only


@admin.register(BackupSchedule)
class BackupScheduleAdmin(admin.ModelAdmin):
    list_display  = ('frequency', 'is_active', 'created_by', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')

    def has_add_permission(self, request):
        # Only one schedule row (pk=1) should exist; prevent creating extras.
        return not BackupSchedule.objects.exists()


@admin.register(BackupRecord)
class BackupRecordAdmin(admin.ModelAdmin):
    list_display  = ('filename', 'backup_type', 'status_badge', 'size_display', 'created_by', 'created_at')
    list_filter   = ('status', 'backup_type')
    search_fields = ('filename',)
    readonly_fields = ('filename', 'filepath', 'size_bytes', 'backup_type',
                       'status', 'error_message', 'created_by', 'created_at')
    ordering      = ('-created_at',)
    list_per_page = 30

    def status_badge(self, obj):
        colours = {
            'success':     ('#065f46', '#d1fae5'),
            'failed':      ('#991b1b', '#fee2e2'),
            'in_progress': ('#92400e', '#fef3c7'),
        }
        fg, bg = colours.get(obj.status, ('#374151', '#f1f5f9'))
        return format_html(
            '<span style="background:{};color:{};padding:2px 8px;'
            'border-radius:10px;font-size:11px;font-weight:600">{}</span>',
            bg, fg, obj.get_status_display(),
        )
    status_badge.short_description = 'Status'

    def size_display(self, obj):
        return obj.size_display
    size_display.short_description = 'Size'

    def has_add_permission(self, request):
        return False  # records are created by the backup engine only
