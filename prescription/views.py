from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from opd.models import OPDVisit
from .models import Prescription, PrescriptionMedicine
from core.services import opd_to_dict
from django.db import transaction

from pharmacy.services import (
    match_pharmacy_item,
    notify_prescription_medicine,
    sync_pharmacy_stock_notifications,
)
from core.rbac import require_module



def _save_medicine_lines(prescription, post_data):
    names = post_data.getlist('med_name')
    dosages = post_data.getlist('med_dosage')
    qtys = post_data.getlist('med_qty')
    prescription.medicine_lines.all().delete()
    for name, dosage, qty in zip(names, dosages, qtys):
        name = name.strip()
        if not name:
            continue
        item = match_pharmacy_item(name)
        line = PrescriptionMedicine.objects.create(
            prescription=prescription,
            medicine_name=name,
            dosage=dosage,
            quantity=int(qty or 1),
            pharmacy_item=item,
        )
        notify_prescription_medicine(line)
    sync_pharmacy_stock_notifications()


@require_module('prescription', level='view')
def list_view(request):
    q = request.GET.get('q', '').strip()
    referral = request.GET.get('referral', '').strip()
    visits = OPDVisit.objects.select_related('patient').prefetch_related('prescription').order_by('-date', '-time')
    if q:
        visits = visits.filter(
            Q(opd_no__icontains=q) | Q(patient__name__icontains=q) |
            Q(patient__uhid__icontains=q) | Q(patient__mobile__icontains=q)
        )
    if referral:
        visits = visits.filter(referral__icontains=referral)

    # Distinct referral doctors for filter dropdown
    referral_doctors = (
        OPDVisit.objects.exclude(referral='')
        .values_list('referral', flat=True)
        .distinct()
        .order_by('referral')
    )

    records = [opd_to_dict(v) for v in visits[:200]]
    return render(request, 'prescription/list.html', {
        'active_sidebar': 'prescription',
        'records': records,
        'q': q,
        'referral_doctors': referral_doctors,
        'selected_referral': referral,
    })


@require_module('prescription', level='full')
def detail(request, pk):
    visit = get_object_or_404(OPDVisit.objects.select_related('patient'), pk=pk)
    pres, _ = Prescription.objects.get_or_create(opd_visit=visit)
    if request.method == 'POST':
        pres.diagnosis = request.POST.get('diagnosis', '')
        pres.medicines = request.POST.get('medicines', '')
        pres.advice = request.POST.get('advice', '')
        pres.save()
        _save_medicine_lines(pres, request.POST)
        messages.success(request, 'Prescription saved. Pharmacy team has been notified of required medicines.')
        return redirect('prescription:detail', pk=pk)
    record = opd_to_dict(visit)
    medicine_lines = pres.medicine_lines.all()
    return render(request, 'prescription/detail.html', {
        'active_sidebar': 'prescription',
        'record': record,
        'pres': pres,
        'medicine_lines': medicine_lines,
    })


@require_module('prescription', level='view')
def print_view(request, pk):
    visit = get_object_or_404(OPDVisit.objects.select_related('patient'), pk=pk)
    pres = Prescription.objects.filter(opd_visit=visit).first()
    medicine_lines = pres.medicine_lines.all() if pres else []
    return render(request, 'prescription/print.html', {
        'record': opd_to_dict(visit),
        'visit': visit,
        'patient': visit.patient,
        'prescription': pres,
        'medicine_lines': medicine_lines,
    })


@require_module('pharmacy', level='full')
def dispense_medicine(request, line_id):
    line = get_object_or_404(PrescriptionMedicine, pk=line_id)

    # Determine where to redirect back — the prescription detail page if possible
    visit_id = getattr(line.prescription, 'opd_visit_id', None)

    if line.pharmacy_item_id:
        qty = int(line.quantity)
        with transaction.atomic():
            item_locked = (
                line.pharmacy_item.__class__.objects.select_for_update().get(pk=line.pharmacy_item_id)
            )
            if item_locked.stock < qty:
                messages.error(
                    request,
                    f'Insufficient stock for {line.medicine_name}. Available: {item_locked.stock}, Required: {qty}.',
                )
                if visit_id:
                    return redirect('prescription:detail', pk=visit_id)
                return redirect('prescription:list')

            item_locked.stock = item_locked.stock - qty
            item_locked.save(update_fields=['stock'])

            line.status = PrescriptionMedicine.STATUS_DISPENSED
            line.save(update_fields=['status'])
            messages.success(request, f'{line.medicine_name} dispensed to {line.prescription.patient.name}.')
    else:
        line.status = PrescriptionMedicine.STATUS_DISPENSED
        line.save(update_fields=['status'])
        messages.warning(request, 'Marked dispensed (no pharmacy item linked).')

    sync_pharmacy_stock_notifications()
    if visit_id:
        return redirect('prescription:detail', pk=visit_id)
    return redirect('prescription:list')

