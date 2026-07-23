from django.db import models
from django.contrib.auth.models import User
from simple_history.models import HistoricalRecords
from uhid.models import Patient


class Bed(models.Model):
    STATUS_CHOICES = [('Occupied', 'Occupied'), ('Vacant', 'Vacant'), ('Maintenance', 'Maintenance')]

    room_no = models.CharField(max_length=20)
    bed_no = models.CharField(max_length=20)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Vacant')
    patient = models.ForeignKey(Patient, on_delete=models.SET_NULL, null=True, blank=True)

    history = HistoricalRecords()

    class Meta:
        unique_together = [['room_no', 'bed_no']]

    @property
    def occupied(self):
        return self.status == 'Occupied'

    @property
    def patient_name(self):
        return self.patient.name if self.patient else ''



class Notification(models.Model):

    TYPE_PHARMACY_LOW = 'pharmacy_low'
    TYPE_PRESCRIPTION = 'prescription_required'
    TYPE_GENERAL = 'general'

    TYPE_CHOICES = [
        (TYPE_PHARMACY_LOW, 'Low Pharmacy Stock'),
        (TYPE_PRESCRIPTION, 'Prescription Medicine Required'),
        (TYPE_GENERAL, 'General'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=30, choices=TYPE_CHOICES, default=TYPE_GENERAL)
    link = models.CharField(max_length=300, blank=True)
    is_read = models.BooleanField(default=False)
    reference_id = models.CharField(max_length=50, blank=True, help_text='Unique key to avoid duplicate alerts')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['is_read', '-created_at'])]

    def __str__(self):
        return self.title
