from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin
from .models import Patient


@admin.register(Patient)
class PatientAdmin(SimpleHistoryAdmin):
    list_display = ('uhid', 'name', 'gender', 'mobile', 'age_years', 'created_at')
    search_fields = ('uhid', 'name', 'mobile')
    list_filter = ('gender', 'marital_status')
