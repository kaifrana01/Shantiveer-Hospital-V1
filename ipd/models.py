from django.db import models
from simple_history.models import HistoricalRecords
from uhid.models import Patient


class IPDAdmission(models.Model):
    STATUS_CHOICES = [('Admitted', 'Admitted'), ('Discharged', 'Discharged')]

    ipd_no = models.CharField(max_length=20, unique=True, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='ipd_admissions')
    date = models.DateField()
    time = models.TimeField(null=True, blank=True)
    guardian = models.CharField(max_length=200, blank=True)
    category = models.CharField(max_length=50, default='General')
    consultant = models.CharField(max_length=200, blank=True)
    kyc_type = models.CharField(max_length=50, blank=True)
    kyc_no = models.CharField(max_length=50, blank=True)
    room_category = models.CharField(max_length=100, blank=True)
    room_no = models.CharField(max_length=20, blank=True)
    diagnosis = models.TextField(blank=True)
    tpa = models.CharField(max_length=200, blank=True)
    policy_no = models.CharField(max_length=100, blank=True)
    insurance_co = models.CharField(max_length=200, blank=True)
    referral = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Admitted')
    created_at = models.DateTimeField(auto_now_add=True)
    bed_charge = models.DecimalField(
    max_digits=10,
    decimal_places=2,
    default=0)

    # Full audit trail — particularly important here since this model
    # carries tpa/policy_no/insurance_co, the fields a CRO will ask
    # "who changed this and when" about during a claims dispute.
    history = HistoricalRecords()

    class Meta:
        ordering = ['-date']

    def save(self, *args, **kwargs):
        if not self.ipd_no:
            from django.db import transaction as _tx
            with _tx.atomic():
                from django.db.models import Max
                import re
                max_row = IPDAdmission.objects.select_for_update().aggregate(m=Max('ipd_no'))['m']
                if max_row:
                    nums = re.findall(r'\d+', max_row)
                    n = int(nums[-1]) + 1 if nums else IPDAdmission.objects.count() + 100
                else:
                    n = 100
                self.ipd_no = f'IPD{n}'
        super().save(*args, **kwargs)

    def __str__(self):
        return self.ipd_no


class IPDPayment(models.Model):
    admission = models.ForeignKey(IPDAdmission, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_mode = models.CharField(max_length=20, default='Cash')
    upi_id = models.CharField(max_length=200, blank=True, help_text='UPI ID used for payment (for UPI mode).')
    remarks = models.CharField(max_length=300, blank=True)
    paid_at = models.DateTimeField(auto_now_add=True)
    # Field exists in the DB (added manually via SQL). Keep it here so Django
    # includes it in every INSERT and doesn't hit OperationalError 1364.
    is_opd_carry_forward = models.BooleanField(default=False)


    history = HistoricalRecords()


class IPDMedicineLine(models.Model):
    admission = models.ForeignKey(IPDAdmission, on_delete=models.CASCADE, related_name='medicine_lines')
    medicine_name = models.CharField(max_length=200)
    quantity = models.PositiveIntegerField(default=1)
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    # Each medicine line posts a debit to income.LedgerEntry — same
    # audit-trail standard as IPDPayment above.
    history = HistoricalRecords()

    def save(self, *args, **kwargs):
        self.amount = self.quantity * self.rate
        super().save(*args, **kwargs)


class DischargeSummary(models.Model):
    admission = models.OneToOneField(IPDAdmission, on_delete=models.CASCADE, related_name='discharge')
    discharge_date = models.DateField()
    notes = models.TextField(blank=True)

    history = HistoricalRecords()
