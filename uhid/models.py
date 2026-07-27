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
            # Generate a unique UHID safely under concurrent load.
            #
            # uhid is a CharField and some legacy rows have non-numeric values
            # (e.g. patient name used as UHID). Cast('uhid', IntegerField())
            # crashes MySQL on those rows with a data-truncation error, which
            # resets the connection (ERR_CONNECTION_RESET in the browser).
            #
            # Safe approach:
            #   1. Lock all rows first so no concurrent insert can sneak in.
            #   2. Fetch all UHIDs into Python, filter to purely numeric ones,
            #      find the true integer max, and increment.
            #   3. Fall back to a safe starting value if no numeric UHIDs exist.
            from django.db import transaction as _tx
            with _tx.atomic():
                # Lock all patient rows to block concurrent inserts.
                Patient.objects.select_for_update().values('id').first()

                # Pull only numeric-looking UHIDs — filter in the DB with REGEXP
                # so we never pass a non-numeric string to int().
                numeric_uhids = (
                    Patient.objects
                    .filter(uhid__regex=r'^\d+$')
                    .values_list('uhid', flat=True)
                )
                max_uhid = max((int(u) for u in numeric_uhids), default=None)

                if max_uhid is not None:
                    self.uhid = str(max_uhid + 1)
                else:
                    # No numeric UHIDs yet — start the sequence at 10001.
                    self.uhid = '10001'
        super().save(*args, **kwargs)

    @property
    def age_display(self):
        if self.age_years > 0:
            return str(self.age_years)
        return f'{self.age_years}Y {self.age_months}M {self.age_days}D'

    def __str__(self):
        return f'{self.name} ({self.uhid})'
