import uuid
from django.db import models
from simple_history.models import HistoricalRecords


class Patient(models.Model):
    GENDER_CHOICES = [('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other')]
    MARITAL_CHOICES = [('Single', 'Single'), ('Married', 'Married')]

    uhid = models.CharField(max_length=20, unique=True, editable=False)
    title = models.CharField(max_length=10, default='Mr')
    name = models.CharField(max_length=200)
    guardian = models.CharField(max_length=200, blank=True)
    guardian_relation = models.CharField(max_length=10, default='S/o')
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, default='Male')
    marital_status = models.CharField(max_length=20, choices=MARITAL_CHOICES, default='Single')
    dob = models.DateField(null=True, blank=True)
    age_years = models.PositiveIntegerField(default=0)
    age_months = models.PositiveIntegerField(default=0)
    age_days = models.PositiveIntegerField(default=0)
    mobile = models.CharField(max_length=15)
    blood_group = models.CharField(max_length=5, default='NA')
    resident = models.CharField(max_length=50, default='India')
    state = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Audit trail: who changed what, and when, for every insert/update/delete.
    # HistoryRequestMiddleware (see settings.MIDDLEWARE) attaches the
    # logged-in user automatically.
    history = HistoricalRecords()

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.uhid:
            # Use database MAX to avoid race condition from count()
            from django.db.models import Max
            max_val = Patient.objects.aggregate(m=Max('uhid'))['m']
            if max_val and str(max_val).isdigit():
                self.uhid = str(int(max_val) + 1)
            else:
                self.uhid = str(Patient.objects.count() + 3490)
        super().save(*args, **kwargs)

    @property
    def age_display(self):
        if self.age_years:
            return str(self.age_years)
        return f'{self.age_years}Y {self.age_months}M {self.age_days}D'

    def __str__(self):
        return f'{self.name} ({self.uhid})'
