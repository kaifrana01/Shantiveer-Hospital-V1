from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Expense


@admin.register(Expense)
class ExpenseAdmin(SimpleHistoryAdmin):
    list_display = (
        'expense_type',
        'category',
        'date',
        'amount',
        'paid_to',
        'batch_id',
        'created_by',
        'created_at',
    )
    list_filter = ('expense_type', 'category', 'date', 'created_at')
    search_fields = ('paid_to', 'remarks', 'batch_id')
    readonly_fields = ('created_at',)

