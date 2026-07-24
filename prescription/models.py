from django.db import models
from simple_history.models import HistoricalRecords
from opd.models import OPDVisit


class Prescription(models.Model):
    opd_visit = models.OneToOneField(OPDVisit, on_delete=models.CASCADE, related_name='prescription')
    diagnosis = models.TextField(blank=True)
    medicines = models.TextField(blank=True)
    advice = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    history = HistoricalRecords()

    def __str__(self):
        if self.opd_visit_id:
            try:
                return f"Prescription for {self.opd_visit.opd_no}"
            except Exception:
                return f"Prescription #{self.pk} (Missing OPD)"
        return f"Prescription #{self.pk}"

    @property
    def patient(self):
        return self.opd_visit.patient


class PrescriptionMedicine(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_DISPENSED = 'dispensed'
    STATUS_LOW_STOCK = 'low_stock'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_DISPENSED, 'Dispensed'),
        (STATUS_LOW_STOCK, 'Low Stock — Reorder Required'),
    ]

    prescription = models.ForeignKey(Prescription, on_delete=models.CASCADE, related_name='medicine_lines')
    medicine_name = models.CharField(max_length=200)
    dosage = models.CharField(max_length=200, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    pharmacy_item = models.ForeignKey(
        'pharmacy.PharmacyItem', on_delete=models.SET_NULL, null=True, blank=True, related_name='prescription_lines',
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.medicine_name} for {self.prescription.opd_visit.patient.name}'
