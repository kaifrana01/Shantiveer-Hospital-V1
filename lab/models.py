from django.db import models
from simple_history.models import HistoricalRecords
from uhid.models import Patient


class LabTestMaster(models.Model):
    name = models.CharField(max_length=200, unique=True)
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)

    # Rate changes on the test catalog directly affect every future bill —
    # worth a tamper-evident trail of who changed a rate and when.
    history = HistoricalRecords()

    def __str__(self):
        return self.name


class LabInvestigation(models.Model):
    PAYMENT_MODES = [('Cash', 'Cash'), ('UPI', 'UPI'), ('Card', 'Card')]

    bill_no = models.CharField(max_length=20, unique=True, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='lab_bills', null=True, blank=True)
    patient_name = models.CharField(max_length=200)
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

    # LabInvestigation is a billing record (it posts to income.LedgerEntry)
    # just like OPDVisit/IPDPayment/PharmacySale — it needs the same
    # tamper-evident trail, especially since discount/total are editable
    # after the fact via test_edit-style flows.
    history = HistoricalRecords()

    class Meta:
        ordering = ['-test_date']

    def save(self, *args, **kwargs):
        if not self.bill_no:
            from django.db.models import Max
            import re
            max_row = LabInvestigation.objects.aggregate(m=Max('bill_no'))['m']
            if max_row:
                nums = re.findall(r'\d+', max_row)
                n = int(nums[-1]) + 1 if nums else LabInvestigation.objects.count() + 1
            else:
                n = 1
            self.bill_no = f'LAB{n:03d}'
        super().save(*args, **kwargs)


class LabInvestigationItem(models.Model):
    investigation = models.ForeignKey(LabInvestigation, on_delete=models.CASCADE, related_name='items')
    test = models.ForeignKey(LabTestMaster, on_delete=models.CASCADE)
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    history = HistoricalRecords()

    def save(self, *args, **kwargs):
        self.amount = self.rate * self.quantity
        super().save(*args, **kwargs)



class LabTestResult(models.Model):
    investigation_item = models.ForeignKey(LabInvestigationItem, on_delete=models.CASCADE, related_name='results')
    result_value = models.CharField(max_length=200, blank=True)
    unit = models.CharField(max_length=50, blank=True)
    reference_range = models.CharField(max_length=200, blank=True)

    # Clinical result values are exactly the kind of record a hospital
    # needs to prove wasn't silently altered after the fact.
    history = HistoricalRecords()
