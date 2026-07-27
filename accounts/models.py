from django.db import models

# Create your models here.


from django.contrib.auth.models import User

class UserProfile(models.Model):
    BLOOD_GROUP_CHOICES = [
        ('A+', 'A+'), ('A-', 'A-'),
        ('B+', 'B+'), ('B-', 'B-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'),
        ('O+', 'O+'), ('O-', 'O-'),
    ]
    GENDER_CHOICES = [
        ('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')

    # ── Personal ──────────────────────────────────────────────
    phone           = models.CharField(max_length=15, blank=True)
    alternate_phone = models.CharField(max_length=15, blank=True)
    date_of_birth   = models.DateField(null=True, blank=True)
    gender          = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
    blood_group     = models.CharField(max_length=5, choices=BLOOD_GROUP_CHOICES, blank=True)
    address         = models.TextField(blank=True)
    emergency_contact = models.CharField(max_length=100, blank=True)
    profile_photo   = models.ImageField(upload_to='profile_photos/', null=True, blank=True)

    # ── Employment ─────────────────────────────────────────────
    designation     = models.CharField(max_length=100, blank=True)
    department      = models.CharField(max_length=100, blank=True)
    specialization  = models.CharField(max_length=100, blank=True)
    qualification   = models.CharField(max_length=200, blank=True)
    employee_code   = models.CharField(max_length=50, blank=True)
    joining_date    = models.DateField(null=True, blank=True)

    # ── Identity / Social ──────────────────────────────────────
    username_handle = models.CharField(max_length=60, blank=True, help_text='e.g. @mchdkaif')

    # ── Documents (stored as file uploads) ─────────────────────
    document_1      = models.FileField(upload_to='profile_docs/', null=True, blank=True)
    document_1_name = models.CharField(max_length=100, blank=True)
    document_2      = models.FileField(upload_to='profile_docs/', null=True, blank=True)
    document_2_name = models.CharField(max_length=100, blank=True)
    document_3      = models.FileField(upload_to='profile_docs/', null=True, blank=True)
    document_3_name = models.CharField(max_length=100, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Profile — {self.user.get_full_name() or self.user.username}'

    @property
    def documents(self):
        docs = []
        for i in (1, 2, 3):
            f = getattr(self, f'document_{i}')
            n = getattr(self, f'document_{i}_name')
            if f:
                docs.append({'file': f, 'name': n or f'Document {i}'})
        return docs
