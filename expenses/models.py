import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from simple_history.models import HistoricalRecords


class Expense(models.Model):
    class Meta:
        app_label = 'expenses'

    class ExpenseType(models.TextChoices):
        BASIC = 'basic', 'Basic Expenses'
        ADVANCE = 'advance', 'Advance Expenses'

    class BasicCategory(models.TextChoices):
        CUT = 'cut', 'Cut'
        PHARMACY = 'pharmacy', 'Pharmacy'
        STATIONARY = 'stationary', 'Stationary'
        LAB = 'lab', 'Lab'
        CANTEEN = 'canteen', 'Canteen'
        # BUG-15 NOTE: the stored DB value is 'mess_charges' (unchanged to
        # preserve existing data).  The display label has been updated to
        # 'MISC Charges' as requested.  The Python attribute is renamed to
        # MISC_CHARGES for clarity; the DB value stays 'mess_charges'.
        MISC_CHARGES = 'mess_charges', 'MISC Charges'
        SALARY = 'salary', 'Salary'
        ADVANCE_SALARY = 'advance_salary', 'Advance Salary'
        # BUG-14 FIX: was labeled 'OT' which in a hospital means "Operating
        # Theatre" — renamed to 'Other' to avoid confusion with OT charges.
        # The DB value ('ot') is unchanged so existing rows are unaffected.
        OTHER = 'ot', 'Other'

    class AdvanceCategory(models.TextChoices):
        RENT = 'rent', 'Rent'
        EXTRA_MATERIAL = 'extra_material', 'Extra Material'

    expense_type = models.CharField(max_length=20, choices=ExpenseType.choices)

    # Keep one category field but constrain via app/form logic.
    category = models.CharField(max_length=50)

    date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    remarks = models.TextField(blank=True)
    paid_to = models.CharField(
        max_length=150,
        blank=True,
        help_text='Person / party this amount was given to (e.g. staff name, vendor, patient).',
    )
    batch_id = models.UUIDField(
        null=True,
        blank=True,
        db_index=True,
        help_text='Groups rows created together in a single form submission so they render as one table row.',
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='expenses_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['expense_type', 'category', 'date']),
        ]

    def __str__(self):
        return f'{self.get_expense_type_display()} - {self.category} - {self.amount}'

