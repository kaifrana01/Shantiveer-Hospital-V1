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
            # IMPORTANT: uhid is a CharField, so lexicographic ordering is
            # unreliable (e.g. '10000' < '9999' as strings). We must cast to
            # integer before finding the max, otherwise two concurrent requests
            # can both read the same "last" value and produce a duplicate UHID
            # (IntegrityError 1062).
            #
            # Fix: use a DB-level CAST to get the true numeric maximum, then
            # lock *all* existing rows with select_for_update() so no other
            # transaction can insert until we commit. The inner atomic() block
            # escalates to a savepoint when called from inside an existing
            # transaction (e.g. opd/views.py or ipd/views.py).
            from django.db import transaction as _tx
            from django.db.models.functions import Cast
            from django.db.models import IntegerField, Max
            with _tx.atomic():
                # Lock all patient rows to block concurrent inserts.
                Patient.objects.select_for_update().values('id').first()

                # Find the true numeric maximum across all UHID values.
                result = (
                    Patient.objects
                    .annotate(uhid_int=Cast('uhid', IntegerField()))
                    .aggregate(max_uhid=Max('uhid_int'))
                )
                max_uhid = result.get('max_uhid')
                if max_uhid is not None:
                    self.uhid = str(max_uhid + 1)
                else:
                    # No patients yet — start the sequence at 10001.
                    self.uhid = '10001'
        super().save(*args, **kwargs)

    @property
    def age_display(self):
        if self.age_years > 0:
            return str(self.age_years)
        return f'{self.age_years}Y {self.age_months}M {self.age_days}D'

    def __str__(self):
        return f'{self.name} ({self.uhid})'
