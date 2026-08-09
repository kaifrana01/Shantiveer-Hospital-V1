import uuid
from decimal import Decimal

from django import forms

from .models import Expense


class _BaseExpenseForm(forms.Form):
    date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}))
    remarks = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Any general note for this entry...'}),
    )

    # Subclasses set this: list of (field_name, CategoryChoice)
    category_fields = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Build one Amount field + one Name ("paid to") field per category,
        # added dynamically so the template can loop over them in pairs.
        for field_name, choice in self.category_fields:
            self.fields[field_name] = forms.DecimalField(
                required=False, max_digits=12, decimal_places=2, min_value=0, initial=0,
                widget=forms.NumberInput(attrs={
                    'class': 'form-control form-control-sm expense-amount',
                    'placeholder': '0.00',
                    'step': '0.01',
                }),
            )
            self.fields[f'{field_name}_name'] = forms.CharField(
                required=False,
                widget=forms.TextInput(attrs={
                    'class': 'form-control form-control-sm expense-name',
                    'placeholder': 'Given to / Paid to...',
                }),
            )

    def rows_meta(self):
        """Yields (label, amount_field, name_field) for template rendering."""
        for field_name, choice in self.category_fields:
            yield choice.label, self[field_name], self[f'{field_name}_name']

    def create_rows(self, *, user):
        if not self.is_valid():
            raise ValueError('Form must be valid before creating rows')

        rows = []
        batch_id = uuid.uuid4()
        base_kwargs = {
            'expense_type': self.expense_type,
            'date': self.cleaned_data['date'],
            'remarks': self.cleaned_data.get('remarks', ''),
            'created_by': user,
            'batch_id': batch_id,
        }

        for field_name, choice in self.category_fields:
            amt = self.cleaned_data.get(field_name) or Decimal('0')
            name = (self.cleaned_data.get(f'{field_name}_name') or '').strip()
            if amt and amt != Decimal('0'):
                rows.append(
                    Expense(category=choice.value, amount=amt, paid_to=name, **base_kwargs)
                )

        if not rows:
            return []

        # Idempotency guard: if an identical submission (same expense_type,
        # date, remarks, and category totals) was already saved within the
        # last 5 seconds by the same user, treat it as a duplicate and
        # return the existing rows instead of inserting again.
        import datetime as _dt
        from django.utils import timezone as _tz
        cutoff = _tz.now() - _dt.timedelta(seconds=5)
        total_amount = sum(r.amount for r in rows)
        recent_duplicate = Expense.objects.filter(
            expense_type=self.expense_type,
            date=self.cleaned_data['date'],
            remarks=self.cleaned_data.get('remarks', ''),
            created_by=user,
            created_at__gte=cutoff,
        ).exists()

        if recent_duplicate:
            # Return empty list — caller shows success but nothing is inserted
            return []

        created = Expense.objects.bulk_create(rows)
        return created


class BasicExpensesForm(_BaseExpenseForm):
    expense_type = Expense.ExpenseType.BASIC
    category_fields = [
        ('cut', Expense.BasicCategory.CUT),
        ('pharmacy', Expense.BasicCategory.PHARMACY),
        ('stationary', Expense.BasicCategory.STATIONARY),
        ('lab', Expense.BasicCategory.LAB),
        ('canteen', Expense.BasicCategory.CANTEEN),
        ('misc_charges', Expense.BasicCategory.MISC_CHARGES),
        ('salary', Expense.BasicCategory.SALARY),
        ('advance_salary', Expense.BasicCategory.ADVANCE_SALARY),
        ('other', Expense.BasicCategory.OTHER),
    ]


class AdvanceExpensesForm(_BaseExpenseForm):
    expense_type = Expense.ExpenseType.ADVANCE
    category_fields = [
        ('rent', Expense.AdvanceCategory.RENT),
        ('extra_material', Expense.AdvanceCategory.EXTRA_MATERIAL),
    ]
