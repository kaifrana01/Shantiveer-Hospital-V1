from django.db import models
from django.contrib.auth.models import User
from simple_history.models import HistoricalRecords


class Doctor(models.Model):
    GENDER_CHOICES = [('M', 'Male'), ('F', 'Female'), ('O', 'Other')]

    name = models.CharField(max_length=200, unique=True)
    department = models.CharField(max_length=150, blank=True)
    specialization = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=15, blank=True)
    email = models.EmailField(max_length=254, blank=True, default='')
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, blank=True, default='')
    qualification = models.CharField(max_length=250, blank=True, default='')
    registration_number = models.CharField(max_length=100, blank=True, default='')
    experience_years = models.PositiveIntegerField(null=True, blank=True)
    date_of_joining = models.DateField(null=True, blank=True)
    dob = models.DateField(null=True, blank=True)
    photo = models.ImageField(upload_to='doctors/', null=True, blank=True)
    address = models.CharField(max_length=300, blank=True, default='')
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='doctor_profile')
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
