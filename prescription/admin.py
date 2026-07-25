from django.contrib import admin
from django.utils.html import format_html
from .models import Prescription, PrescriptionMedicine


class PrescriptionMedicineInline(admin.TabularInline):
    model   = PrescriptionMedicine
    extra   = 0
    fields  = ('medicine_name', 'dosage', 'quantity', 'status', 'pharmacy_item')
    readonly_fields = ()


@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    list_display  = ('opd_visit', 'patient_name', 'diagnosis_preview',
                     'medicines_count', 'updated_at')
    search_fields = ('opd_visit__opd_no', 'opd_visit__patient__name',
                     'opd_visit__patient__uhid', 'diagnosis')
    list_filter   = ('updated_at',)
    readonly_fields = ('updated_at',)
    inlines       = [PrescriptionMedicineInline]
    list_per_page = 30
    ordering      = ('-updated_at',)

    def patient_name(self, obj):
        try:
            return obj.opd_visit.patient.name
        except Exception:
            return '—'
    patient_name.short_description = 'Patient'

    def diagnosis_preview(self, obj):
        if obj.diagnosis:
            short = obj.diagnosis[:60] + ('…' if len(obj.diagnosis) > 60 else '')
            return format_html('<span style="font-size:12px">{}</span>', short)
        return format_html('<span style="color:#aaa">—</span>')
    diagnosis_preview.short_description = 'Diagnosis'

    def medicines_count(self, obj):
        count = obj.medicine_lines.count()
        colour = '#065f46' if count > 0 else '#aaa'
        return format_html(
            '<span style="color:{};font-weight:600">{}</span>', colour, count
        )
    medicines_count.short_description = 'Medicines'


@admin.register(PrescriptionMedicine)
class PrescriptionMedicineAdmin(admin.ModelAdmin):
    list_display  = ('medicine_name', 'prescription_opd', 'dosage',
                     'quantity', 'status_badge')
    list_filter   = ('status',)
    search_fields = ('medicine_name', 'prescription__opd_visit__opd_no',
                     'prescription__opd_visit__patient__name')
    list_per_page = 40

    def prescription_opd(self, obj):
        try:
            return obj.prescription.opd_visit.opd_no
        except Exception:
            return '—'
    prescription_opd.short_description = 'OPD No'

    def status_badge(self, obj):
        colours = {
            'pending':   ('#78350f', '#fef3c7'),
            'dispensed': ('#065f46', '#d1fae5'),
            'low_stock': ('#991b1b', '#fee2e2'),
        }
        fg, bg = colours.get(obj.status, ('#374151', '#f1f5f9'))
        return format_html(
            '<span style="background:{};color:{};padding:2px 9px;'
            'border-radius:12px;font-size:11px">{}</span>',
            bg, fg, obj.get_status_display(),
        )
    status_badge.short_description = 'Status'
