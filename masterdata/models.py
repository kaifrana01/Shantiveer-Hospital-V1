from django.db import models
from simple_history.models import HistoricalRecords


class Doctor(models.Model):
    name = models.CharField(max_length=200, unique=True)
    department = models.CharField(max_length=150, blank=True)
    specialization = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=15, blank=True)
    email = models.EmailField(max_length=254, blank=True, default='')
    address = models.CharField(max_length=300, blank=True, default='')
    is_active = models.BooleanField(default=True)

    history = HistoricalRecords()

    def __str__(self):
        return self.name


class TestInterpretation(models.Model):
    test_name = models.CharField(max_length=300)
    interpretation = models.TextField()
    status = models.CharField(max_length=20, default='Active')
    created_at = models.DateTimeField(auto_now_add=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ['test_name']

    def __str__(self):
        return self.test_name
