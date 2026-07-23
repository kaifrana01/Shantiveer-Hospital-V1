from django.db import models
from django.contrib.auth.models import User


class BackupSchedule(models.Model):
    FREQUENCY_CHOICES = [
        ('manual', 'Manual Only'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    ]

    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='manual')
    is_active = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Backup Schedule'

    def __str__(self):
        return f'Backup Schedule ({self.frequency})'


class BackupRecord(models.Model):
    STATUS_CHOICES = [
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('in_progress', 'In Progress'),
    ]
    TYPE_CHOICES = [
        ('manual', 'Manual'),
        ('daily', 'Daily Auto'),
        ('weekly', 'Weekly Auto'),
        ('monthly', 'Monthly Auto'),
        ('yearly', 'Yearly Auto'),
    ]

    filename = models.CharField(max_length=300)
    filepath = models.CharField(max_length=500)
    size_bytes = models.BigIntegerField(default=0)
    backup_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='manual')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in_progress')
    error_message = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.filename

    @property
    def size_display(self):
        size = self.size_bytes
        if size >= 1024 * 1024:
            return f'{size / (1024 * 1024):.1f} MB'
        elif size >= 1024:
            return f'{size / 1024:.1f} KB'
        return f'{size} B'
