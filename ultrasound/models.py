"""
Ultrasound module models — completely independent from other HMS modules.
Has its own data, billing, and financial tracking.
"""
from django.db import models
from simple_history.models import HistoricalRecords

from uhid.models import Patient


class UltrasoundTestMaster(models.Model):
    """Catalog of ultrasound scan options and their standard fee."""
    name = models.CharField(max_length=200, unique=True)
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ['name']
        verbose_name = 'Ultrasound Test'
        verbose_name_plural = 'Ultrasound Tests'

    def __str__(self):
        return self.name


class UltrasoundExpense(models.Model):
    """Ultrasound-specific expenses (reagents, maintenance, consumables, etc.)."""

    CATEGORY_CHOICES = [
        ('consumables', 'Consumables / Gel'),
        ('maintenance', 'Machine Maintenance'),
        ('staff', 'Staff / Salary'),
        ('utilities', 'Utilities'),
        ('other', 'Other'),
    ]

    date = models.DateField()
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default='other')
    description = models.CharField(max_length=300)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.date} – {self.category} – ₹{self.amount}"


class UltrasoundInvestigation(models.Model):
    """One ultrasound billing encounter."""
    PAYMENT_MODES = [('Cash', 'Cash'), ('UPI', 'UPI'), ('Card', 'Card')]

    bill_no = models.CharField(max_length=20, unique=True, editable=False)
    patient = models.ForeignKey(
        Patient, on_delete=models.SET_NULL,
        related_name='ultrasound_bills', null=True, blank=True,
    )
    patient_name = models.CharField(max_length=200)
    age = models.CharField(max_length=10, blank=True)
    gender = models.CharField(max_length=10, blank=True, choices=[
        ('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other')
    ])
    mobile = models.CharField(max_length=15, blank=True)
    address = models.TextField(blank=True)
    consultant = models.CharField(max_length=200, default='-- Self --')
    referred_by = models.CharField(max_length=200, default='SELF')
    remarks = models.TextField(blank=True)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_mode = models.CharField(max_length=20, default='Cash')
    test_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ['-test_date', '-created_at']

    def save(self, *args, **kwargs):
        if not self.bill_no:
            from django.db import transaction as _tx
            with _tx.atomic():
                # CharField Max('bill_no') is lexicographic ('USG9999' > 'USG10000'),
                # so we pull all bill_no values and find the true integer max in Python.
                UltrasoundInvestigation.objects.select_for_update().values('id').first()
                numeric_nos = (
                    UltrasoundInvestigation.objects
                    .filter(bill_no__regex=r'^USG\d+$')
                    .values_list('bill_no', flat=True)
                )
                max_n = max(
                    (int(no[3:]) for no in numeric_nos if no[3:].isdigit()),
                    default=0,
                )
                self.bill_no = f'USG{max_n + 1:04d}'
        super().save(*args, **kwargs)

    def __str__(self):
        return self.bill_no


class UltrasoundInvestigationItem(models.Model):
    """Line item on an ultrasound bill."""
    investigation = models.ForeignKey(
        UltrasoundInvestigation, on_delete=models.CASCADE, related_name='items',
    )
    test = models.ForeignKey(UltrasoundTestMaster, on_delete=models.CASCADE)
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    history = HistoricalRecords()

    class Meta:
        # DB-level guard: one line per test per bill — prevents duplicate items
        # even if the view logic fails to deduplicate.
        unique_together = ('investigation', 'test')

    def save(self, *args, **kwargs):
        self.amount = self.rate * self.quantity
        super().save(*args, **kwargs)


class UltrasoundDocument(models.Model):
    """Uploaded report file attached to a bill."""
    investigation = models.ForeignKey(
        UltrasoundInvestigation, on_delete=models.CASCADE, related_name='documents',
    )
    file = models.FileField(upload_to='ultrasound_documents/%Y/%m/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.file.name
