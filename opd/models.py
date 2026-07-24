from django.db import models
from simple_history.models import HistoricalRecords
from uhid.models import Patient
from lab.models import LabTestMaster


class OPDVisit(models.Model):
    PAYMENT_MODES = [('Cash', 'Cash'), ('UPI', 'UPI'), ('Card', 'Card'), ('Cheque', 'Cheque')]

    opd_no = models.CharField(max_length=20, unique=True, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='opd_visits')
    date = models.DateField()
    time = models.TimeField()
    referral = models.CharField(max_length=200, blank=True)
    doctor_name = models.CharField(max_length=200, blank=True)
    fees = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    head = models.CharField(max_length=200, default='Opd Consultation')
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_mode = models.CharField(max_length=20, choices=PAYMENT_MODES, default='Cash')
    upi_id = models.CharField(max_length=200, blank=True, help_text='UPI ID used for payment (for UPI mode).')
    reference_info = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ['-date', '-time']

    def save(self, *args, **kwargs):
        if not self.opd_no:
            from django.db import transaction as _tx
            with _tx.atomic():
                from django.db.models import Max
                import re
                max_row = OPDVisit.objects.select_for_update().aggregate(m=Max('opd_no'))['m']
                if max_row:
                    nums = re.findall(r'\d+', max_row)
                    n = int(nums[-1]) + 1 if nums else OPDVisit.objects.count() + 1
                else:
                    n = 1
                self.opd_no = f'OPD{n:03d}'
        super().save(*args, **kwargs)

    def __str__(self):
        return self.opd_no


class OPDVisitTestItem(models.Model):
    """Selected OPD tests with qty and rate snapshot."""

    opd_visit = models.ForeignKey(OPDVisit, on_delete=models.CASCADE, related_name='test_items')
    test = models.ForeignKey(LabTestMaster, on_delete=models.PROTECT)

    # snapshot
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    history = HistoricalRecords()

    class Meta:
        unique_together = ('opd_visit', 'test')

    def save(self, *args, **kwargs):
        self.amount = (self.rate or 0) * (self.quantity or 0)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.opd_visit.opd_no} - {self.test.name}" 

