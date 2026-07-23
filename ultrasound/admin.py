from django.contrib import admin
from .models import (
    UltrasoundTestMaster,
    UltrasoundInvestigation,
    UltrasoundInvestigationItem,
    UltrasoundDocument,
    UltrasoundExpense,
)


@admin.register(UltrasoundTestMaster)
class UltrasoundTestMasterAdmin(admin.ModelAdmin):
    list_display = ['name', 'rate', 'is_active']
    list_filter  = ['is_active']
    search_fields = ['name']


class UltrasoundItemInline(admin.TabularInline):
    model = UltrasoundInvestigationItem
    extra = 0


@admin.register(UltrasoundInvestigation)
class UltrasoundInvestigationAdmin(admin.ModelAdmin):
    list_display  = ['bill_no', 'patient_name', 'test_date', 'total', 'payment_mode']
    list_filter   = ['payment_mode', 'test_date']
    search_fields = ['bill_no', 'patient_name', 'mobile']
    inlines       = [UltrasoundItemInline]
    readonly_fields = ['bill_no', 'created_at']


@admin.register(UltrasoundExpense)
class UltrasoundExpenseAdmin(admin.ModelAdmin):
    list_display  = ['date', 'category', 'description', 'amount']
    list_filter   = ['category', 'date']
    search_fields = ['description']
