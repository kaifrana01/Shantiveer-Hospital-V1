from decimal import Decimal
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from uhid.models import Patient
from income.models import LedgerEntry, validate_payment_amount, validate_payment_mode, PAYMENT_MODES_ALL
from .models import IPDAdmission, IPDPayment, IPDMedicineLine, DischargeSummary, IPDDocument
from core.models import Bed
from core.rbac import require_module


def _cap_text(s):
    if s is None:
        return ''
    return str(s).strip().title()


def _normalize_category(raw):
    """Map raw category input to a consistent stored value."""
    norm = (raw or '').strip().lower()
    if norm in {'icu', 'emergency', 'emerg', 'er', 'emergency/icu', 'icu ward', 'emergency ward'}:
        return 'ICU'
    if 'private' in norm:
        return 'Private Ward'
    if 'general' in norm:
        return 'General Ward'
    return _cap_text(raw) if raw else 'General Ward'


def _ipd_dict(a):
    return {
        'id': a.id,
        'name': a.patient.name,
        'age': a.patient.age_years,
        'gender': a.patient.gender.upper(),
        'uhid': a.patient.uhid,
        'ipd_no': a.ipd_no,
        'consultant': a.consultant,
        'room': a.room_no,
        'diagnosis': a.diagnosis,
        'date': str(a.date),
        'status': a.status,
        'category': a.category,
    }


def _get_bed_charge_details(adm, discharge_date=None):
    """Return (rate_per_day, days_stayed, total_bed_charge) for an admission.

    bed_charge stores the *per-day* rate entered at admission.
    If no rate was entered, rate is 0 — no silent defaults applied.
    """
    from datetime import date as _date
    # Use whatever rate was entered at admission. Zero if not set.
    rate_per_day = Decimal(str(adm.bed_charge)) if adm.bed_charge and adm.bed_charge > 0 else Decimal('0')

    # Determine end date: prefer the explicit discharge_date argument, then
    # the DischargeSummary record, and fall back to today for admitted patients.
    if discharge_date is None:
        try:
            discharge_date = adm.discharge.discharge_date
        except Exception:
            discharge_date = _date.today()

    admission_date = adm.date
    days = max(1, (discharge_date - admission_date).days)

    return rate_per_day, days, rate_per_day * days


def _compute_ipd_bill_total(adm, discharge_date=None):
    """Compute total IPD bill: (bed_charge_per_day × days) + doctor fees + medicines.

    Uses admission.bed_charge as the *per-day* rate. Falls back to ward-based
    per-day defaults when bed_charge is not set.
    Uses admission.doctor_fees for the consultant fee (editable per patient).
    """
    _rate, _days, room_amount = _get_bed_charge_details(adm, discharge_date)

    # Use the per-admission doctor_fees field. Zero if not set.
    doctor_fees = adm.doctor_fees if adm.doctor_fees else Decimal('0')

    med_total = sum(m.amount for m in adm.medicine_lines.all()) or Decimal('0.00')
    return room_amount + doctor_fees + med_total


@require_module('ipd_list', level='view')
def patient_list(request):
    q = request.GET.get('q', '').strip()
    referral = request.GET.get('referral', '').strip()

    qs = IPDAdmission.objects.select_related('patient').filter(status='Admitted')
    if q:
        qs = qs.filter(
            Q(patient__name__icontains=q)
            | Q(ipd_no__icontains=q)
            | Q(patient__uhid__icontains=q)
        )
    if referral:
        qs = qs.filter(referral__icontains=referral)

    qs = qs.annotate(advance_paid=Sum('payments__amount'))

    # Distinct referral doctors for filter dropdown
    referral_doctors = (
        IPDAdmission.objects.filter(status='Admitted', referral__isnull=False)
        .exclude(referral='')
        .values_list('referral', flat=True)
        .distinct()
        .order_by('referral')
    )

    patients = []
    for a in qs:
        total_amount = _compute_ipd_bill_total(a)
        advance_paid = a.advance_paid or Decimal('0.00')
        due_amount = total_amount - advance_paid
        d = _ipd_dict(a)
        d.update({
            'total_amount': total_amount,
            'advance_paid': advance_paid,
            'due_amount': due_amount,
        })
        patients.append(d)

    return render(request, 'ipd/patient_list.html', {
        'active_sidebar': 'ipd',
        'patients': patients,
        'referral_doctors': referral_doctors,
        'selected_referral': referral,
    })


@require_module('ipd_admission', level='full')
def admission(request):
    edit_id = request.GET.get('edit') or request.POST.get('edit_id')
    admission_obj = None
    if edit_id:
        admission_obj = IPDAdmission.objects.select_related('patient').filter(pk=edit_id).first()

    if request.method == 'POST':
        # Pre-validate numeric fields before entering the atomic block so we
        # can return clean error messages without rolling anything back.
        try:
            bed_charge = Decimal(request.POST.get('bed_charge') or '0')
            if bed_charge < 0:
                raise ValueError('Bed charge cannot be negative.')
        except (ValueError, Exception) as e:
            messages.error(request, f'Invalid bed charge: {e}')
            return redirect('ipd:admission')

        try:
            doctor_fees = Decimal(request.POST.get('doctor_fees') or '0')
            if doctor_fees < 0:
                raise ValueError('Doctor fees cannot be negative.')
        except (ValueError, Exception) as e:
            messages.error(request, f'Invalid doctor fees: {e}')
            return redirect('ipd:admission')

        adv_raw = (request.POST.get('advance_payment') or '').strip().replace(',', '')
        try:
            adv = Decimal(adv_raw) if adv_raw else Decimal('0.00')
        except Exception:
            adv = Decimal('0.00')

        adv_mode = request.POST.get('advance_payment_mode', 'Cash') or 'Cash'
        try:
            adv_mode = validate_payment_mode(adv_mode, allowed=['Cash', 'UPI', 'Card', 'Cheque'])
        except ValueError:
            adv_mode = 'Cash'
        adv_upi_id = ''
        if adv_mode == 'UPI':
            adv_upi_id = (request.POST.get('advance_upi_id') or '').strip()[:200]

        try:
            # BUG-01 FIX: the entire admission save, bed allocation, advance
            # payment, and income mirroring are now inside a single
            # transaction.atomic() block.  A failure in any step rolls back
            # the whole operation so the DB never ends up in a partial state
            # (e.g. admission created but no bed freed, or payment recorded
            # without an admission to match it).
            with transaction.atomic():
                uhid = (request.POST.get('uhid') or '').strip()
                patient = Patient.objects.filter(uhid=uhid).first() if uhid else None

                # Determine category once, cleanly
                raw_category = request.POST.get('room_category') or request.POST.get('category') or ''
                category = _normalize_category(raw_category)

                if patient:
                    # Update existing patient demographics
                    patient.name = _cap_text(request.POST.get('patient_name', patient.name))
                    patient.mobile = request.POST.get('contact', patient.mobile)
                    patient.gender = _cap_text(request.POST.get('gender', patient.gender))
                    try:
                        patient.age_years = int(request.POST.get('age') or patient.age_years)
                    except (ValueError, TypeError):
                        pass
                    patient.address = _cap_text(request.POST.get('address', patient.address))
                    patient.save()
                else:
                    try:
                        age_val = int(request.POST.get('age') or 0)
                    except (ValueError, TypeError):
                        age_val = 0
                    patient = Patient.objects.create(
                        name=_cap_text(request.POST.get('patient_name', '')),
                        mobile=request.POST.get('contact', ''),
                        gender=_cap_text(request.POST.get('gender', 'Male')),
                        age_years=age_val,
                        address=_cap_text(request.POST.get('address', '')),
                    )

                common_fields = dict(
                    patient=patient,
                    date=request.POST.get('date') or timezone.localdate(),
                    time=request.POST.get('time') or None,
                    guardian=_cap_text(request.POST.get('guardian', '')),
                    category=category,
                    consultant=_cap_text(request.POST.get('consultant', '')),
                    kyc_type=request.POST.get('kyc_type', ''),
                    kyc_no=_cap_text(request.POST.get('kyc_no', '')),
                    room_category=_cap_text(raw_category),
                    room_no=request.POST.get('room_no', ''),
                    diagnosis=_cap_text(request.POST.get('diagnosis', '')),
                    tpa=_cap_text(request.POST.get('tpa', '')),
                    policy_no=_cap_text(request.POST.get('policy_no', '')),
                    insurance_co=_cap_text(request.POST.get('insurance', '')),
                    referral=_cap_text(request.POST.get('referral', '')),
                    status=request.POST.get('status', 'Admitted'),
                    bed_charge=bed_charge,
                    doctor_fees=doctor_fees,
                )

                is_new_admission = admission_obj is None

                if admission_obj:
                    for field, val in common_fields.items():
                        setattr(admission_obj, field, val)
                    admission_obj.save()
                    messages.success(request, 'IPD admission updated.')
                else:
                    admission_obj = IPDAdmission.objects.create(**common_fields)
                    messages.success(request, 'IPD admission saved.')

                # Auto-allocate a vacant bed — only on new admissions.
                room_no = (request.POST.get('room_no') or '').strip()
                if is_new_admission and room_no and admission_obj.status == 'Admitted':
                    vacant_bed = (
                        Bed.objects
                        .select_for_update()
                        .filter(room_no=room_no, status='Vacant')
                        .order_by('bed_no')
                        .first()
                    )
                    if vacant_bed:
                        vacant_bed.status = 'Occupied'
                        vacant_bed.patient = patient
                        vacant_bed.save(update_fields=['status', 'patient'])
                    else:
                        messages.warning(request, f'No vacant bed available in Room {room_no}.')

                # Advance payment — only record on NEW admissions to prevent
                # duplicate payments when editing.
                if is_new_admission and adv > 0:
                    ipd_pay = IPDPayment.objects.create(
                        admission=admission_obj,
                        amount=adv,
                        payment_mode=adv_mode,
                        upi_id=adv_upi_id,
                        remarks=f'Advance payment ({admission_obj.ipd_no})',
                    )
                    LedgerEntry.record_payment(
                        uhid=admission_obj.patient.uhid,
                        amount=adv,
                        payer_type=LedgerEntry.PayerType.PATIENT,
                        payment_mode=adv_mode,
                        description=f'IPD advance payment ({admission_obj.ipd_no})',
                        patient=admission_obj.patient,
                        ipd_admission=admission_obj,
                        source_app='ipd',
                        source_id=str(ipd_pay.id),
                    )
                    # Mirror advance into IncomeEntry for daybook
                    from income.models import IncomeEntry as _IE
                    _IE.objects.create(
                        date=admission_obj.date,
                        category='IPD',
                        patient_name=admission_obj.patient.name,
                        description=f'IPD advance payment ({admission_obj.ipd_no})',
                        payment_mode=adv_mode,
                        amount=adv,
                    )

                # Save uploaded documents — allowed on both new and edited admissions.
                for f in request.FILES.getlist('documents'):
                    IPDDocument.objects.create(
                        admission=admission_obj,
                        file=f,
                        name=f.name,
                    )

            return redirect('ipd:patient_list')
        except Exception as e:
            messages.error(request, f'Error saving admission: {e}')
            return redirect('ipd:admission')

    present = IPDAdmission.objects.filter(status='Admitted').select_related('patient')
    present_list = [
        {'name': a.patient.name, 'room': a.room_no, 'ipd_no': a.ipd_no, 'category': a.category}
        for a in present
    ]

    from masterdata.models import Doctor
    doctors = Doctor.objects.filter(is_active=True).order_by('name')

    # Bed dropdown — vacant beds + the currently occupied bed (so edit works)
    bed_options_qs = Bed.objects.filter(status='Vacant').order_by('room_no', 'bed_no').values('room_no', 'bed_no')
    bed_options = list(bed_options_qs)

    # If editing and a room is already assigned, add it to the list so it shows as selected
    if admission_obj and admission_obj.room_no:
        current_room = admission_obj.room_no
        already_in = any(b['room_no'] == current_room for b in bed_options)
        if not already_in:
            # Find the bed record for the current room
            current_bed = Bed.objects.filter(room_no=current_room).values('room_no', 'bed_no').first()
            if current_bed:
                bed_options.insert(0, current_bed)
            else:
                bed_options.insert(0, {'room_no': current_room, 'bed_no': '—'})

    ctx = {
        'active_sidebar': 'ipd_admission',
        'today': timezone.localdate().isoformat(),
        'present_patients': present_list,
        'ipd_no': admission_obj.ipd_no if admission_obj else f'IPD{IPDAdmission.objects.count() + 101}',
        'form_ipd_no': admission_obj.ipd_no if admission_obj else '',
        'form_bed_charge': getattr(admission_obj, 'bed_charge', None) if admission_obj else '',
        'form_doctor_fees': getattr(admission_obj, 'doctor_fees', '') if admission_obj else '',
        'edit_id': admission_obj.id if admission_obj else '',
        'form_uhid': admission_obj.patient.uhid if admission_obj else '',
        'form_patient_name': admission_obj.patient.name if admission_obj else '',
        'form_age': admission_obj.patient.age_years if admission_obj else '',
        'form_gender': admission_obj.patient.gender.upper() if admission_obj else 'MALE',
        'form_contact': admission_obj.patient.mobile if admission_obj else '',
        'form_address': admission_obj.patient.address if admission_obj else '',
        'form_date': str(admission_obj.date) if admission_obj else '',
        'form_time': admission_obj.time.strftime('%H:%M') if admission_obj and admission_obj.time else '',
        'form_guardian': admission_obj.guardian if admission_obj else '',
        'form_category': admission_obj.category if admission_obj else 'General Ward',
        'form_consultant': admission_obj.consultant if admission_obj else '',
        'form_kyc_type': admission_obj.kyc_type if admission_obj else 'Aadhar',
        'form_kyc_no': admission_obj.kyc_no if admission_obj else '',
        'form_room_category': admission_obj.room_category if admission_obj else '',
        'form_room_no': admission_obj.room_no if admission_obj else '',
        'form_diagnosis': admission_obj.diagnosis if admission_obj else '',
        'form_tpa': admission_obj.tpa if admission_obj else '',
        'form_policy_no': admission_obj.policy_no if admission_obj else '',
        'form_insurance': admission_obj.insurance_co if admission_obj else '',
        'form_referral': admission_obj.referral if admission_obj else '',
        'form_status': admission_obj.status if admission_obj else 'Admitted',
        'doctors': doctors,
        'bed_options': bed_options,
        'existing_documents': list(admission_obj.documents.all()) if admission_obj else [],
    }
    return render(request, 'ipd/admission.html', ctx)


@require_module('billing_collect', level='view')
def payment_total(request):
    ipd_no = (request.GET.get('ipd_no') or '').strip().upper()
    if ipd_no and not ipd_no.startswith('IPD'):
        ipd_no = f'IPD{ipd_no}'

    adm = IPDAdmission.objects.select_related('patient').filter(ipd_no=ipd_no).first()
    if not adm:
        return JsonResponse({'total': '0.00', 'patient_name': '', 'due': '0.00'})

    bill_total = _compute_ipd_bill_total(adm)
    paid_total = adm.payments.aggregate(s=Sum('amount'))['s'] or Decimal('0.00')
    due = max(bill_total - paid_total, Decimal('0.00'))

    return JsonResponse({
        'total': str(due),          # pre-fill with outstanding due
        'bill_total': str(bill_total),
        'paid_total': str(paid_total),
        'due': str(due),
        'patient_name': adm.patient.name,
    })


@require_module('billing_collect', level='full')
def payment(request):
    """IPD payment screen."""
    if request.method == 'POST':
        adm = IPDAdmission.objects.filter(ipd_no=request.POST.get('ipd_no')).first()
        if not adm:
            messages.error(request, 'IPD number not found.')
            return redirect('ipd:payment')

        try:
            amount = validate_payment_amount(request.POST.get('amount', ''))
            mode = validate_payment_mode(request.POST.get('mode', 'Cash'),
                                         allowed=['Cash', 'UPI', 'Card', 'Cheque'])
        except ValueError as e:
            messages.error(request, str(e))
            return redirect('ipd:payment')

        remarks = _cap_text(request.POST.get('remarks', ''))
        upi_id = ''
        if mode == 'UPI':
            upi_id = (request.POST.get('upi_id') or '').strip()[:200]

        with transaction.atomic():
            ipd_pay = IPDPayment.objects.create(
                admission=adm,
                amount=amount,
                payment_mode=mode,
                upi_id=upi_id,
                remarks=remarks,
            )
            LedgerEntry.record_payment(
                uhid=adm.patient.uhid,
                amount=amount,
                payer_type=LedgerEntry.PayerType.PATIENT,
                payment_mode=mode,
                description=remarks or f'IPD payment for {adm.ipd_no}',
                patient=adm.patient,
                ipd_admission=adm,
                source_app='ipd',
                source_id=str(ipd_pay.id),
            )
            # Mirror into IncomeEntry so daybook reflects IPD payments
            from income.models import IncomeEntry as _IE
            _IE.objects.create(
                date=adm.date,
                category='IPD',
                patient_name=adm.patient.name,
                description=remarks or f'IPD payment ({adm.ipd_no})',
                payment_mode=mode,
                amount=amount,
            )
        messages.success(request, 'Payment recorded.')
        from django.urls import reverse
        return redirect(f"{reverse('ipd:bill')}?ipd_no={adm.ipd_no}")

    payments = IPDPayment.objects.select_related('admission__patient').order_by('-paid_at')[:20]
    data = [
        {
            'id':     p.id,
            'ipd_no': p.admission.ipd_no,
            'name':   p.admission.patient.name,
            'amount': p.amount,
            'mode':   p.payment_mode,
            'date':   p.paid_at.date(),
            'remarks': p.remarks,
        }
        for p in payments
    ]
    return render(request, 'ipd/payment.html', {'active_sidebar': 'ipd_payment', 'payments': data})


@require_module('patient_bill', level='view')
def bill(request):
    """
    Read-only bill view. Does NOT post any ledger charges.
    Charges are posted at admission time (advance) and via the payment screen.
    Refreshing this page is safe and idempotent.
    """
    bill_data = None
    ipd_no = request.GET.get('ipd_no')

    if ipd_no:
        ipd_no_norm = ipd_no.strip().upper()
        if ipd_no_norm and not ipd_no_norm.startswith('IPD'):
            ipd_no_norm = f'IPD{ipd_no_norm}'

        adm = IPDAdmission.objects.select_related('patient').filter(ipd_no=ipd_no_norm).first()

        if adm:
            # Canonical billing: bed charge = per-day rate × days stayed
            rate_per_day, days_stayed, room_amount = _get_bed_charge_details(adm)
            doctor_fees = adm.doctor_fees if adm.doctor_fees else Decimal('0')
            med_total = sum(m.amount for m in adm.medicine_lines.all()) or Decimal('0.00')

            bed_desc = f'Bed / Room Charges (₹{rate_per_day} × {days_stayed} day{"s" if days_stayed != 1 else ""})'
            items = [{'desc': bed_desc, 'amount': room_amount},
                     {'desc': 'Doctor / Consultation Fees', 'amount': doctor_fees}]
            if med_total:
                items.append({'desc': 'Medicines', 'amount': med_total})

            total = sum((i['amount'] for i in items), Decimal('0.00'))
            paid_total = adm.payments.aggregate(s=Sum('amount'))['s'] or Decimal('0.00')
            due_amount = total - paid_total

            bill_data = {
                'patient_name': adm.patient.name,
                'patient_age': adm.patient.age_years,
                'patient_gender': adm.patient.gender,
                'patient_uhid': adm.patient.uhid,
                'patient_mobile': adm.patient.mobile,
                'diagnosis': adm.diagnosis,
                'doctor_name': adm.consultant,
                'ipd_no': adm.ipd_no,
                'admission_date': adm.date,
                'room_no': adm.room_no,
                'room_category': adm.room_category,
                'guardian': adm.guardian,
                'status': adm.status,
                'items': items,
                'total': total,
                'paid_total': paid_total,
                'due_amount': due_amount,
            }

    return render(request, 'ipd/bill.html', {'active_sidebar': 'ipd_bill', 'bill': bill_data})


@require_module('ipd_admission', level='view')
def admission_beds(request):
    ward = (request.GET.get('ward') or '').strip().lower()
    if not ward:
        return JsonResponse({'beds': []})

    if 'private' in ward:
        prefix = 'P'
    elif 'emergency' in ward or 'icu' in ward:
        prefix = 'E'
    else:
        prefix = 'G'

    beds_qs = Bed.objects.filter(
        status='Vacant', room_no__istartswith=prefix
    ).order_by('room_no', 'bed_no')
    beds = list(beds_qs.values('room_no', 'bed_no'))
    return JsonResponse({'beds': beds})


@require_module('discharge', level='view')
def discharge_list(request):
    q = request.GET.get('q', '').strip()
    items = DischargeSummary.objects.select_related('admission__patient').order_by('-discharge_date')
    if q:
        items = items.filter(
            Q(admission__ipd_no__icontains=q) | Q(admission__patient__name__icontains=q)
        )
    discharges = [{
        'id': d.id,
        'ipd_no': d.admission.ipd_no,
        'name': d.admission.patient.name,
        'age': d.admission.patient.age_years,
        'gender': d.admission.patient.gender,
        'guardian': d.admission.guardian,
        'room': d.admission.room_no,
        'contact': d.admission.patient.mobile,
        'consultant': d.admission.consultant,
        'discharge_date': str(d.discharge_date),
    } for d in items]
    return render(request, 'ipd/discharge_list.html', {
        'active_sidebar': 'ipd_discharge',
        'discharges': discharges,
        'q': q,
    })


@require_module('discharge', level='full')
def discharge_add(request):
    if request.method == 'POST':
        adm = IPDAdmission.objects.filter(ipd_no=request.POST.get('ipd_no')).first()
        if not adm:
            messages.error(request, 'IPD Number not found. Please check and try again.')
            return redirect('ipd:discharge_list')

        if adm:
            with transaction.atomic():
                # BUG-09 FIX: use update_or_create with all POST fields so
                # that notes/diagnosis entered in the form are actually saved.
                # Previously only discharge_date was passed in defaults={},
                # meaning notes were silently dropped on every submission.
                discharge_date_val = request.POST.get('discharge_date') or timezone.localdate()
                notes_val = (request.POST.get('notes') or '').strip()

                discharge_obj, created = DischargeSummary.objects.update_or_create(
                    admission=adm,
                    defaults={
                        'discharge_date': discharge_date_val,
                        'notes': notes_val,
                    },
                )
                adm.status = 'Discharged'
                adm.save()

                # Free up the bed occupied by this patient
                bed = Bed.objects.filter(
                    room_no=adm.room_no, patient=adm.patient, status='Occupied'
                ).first()
                if bed:
                    bed.status = 'Vacant'
                    bed.patient = None
                    bed.save(update_fields=['status', 'patient'])

            messages.success(request, 'Discharge added.')

            # Validate next URL to prevent open redirect
            next_url = (request.POST.get('next') or '').strip()
            if next_url:
                from django.utils.http import url_has_allowed_host_and_scheme
                if url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                    return redirect(next_url)

        return redirect('ipd:discharge_list')

    # GET — show a discharge form with all admitted patients listed
    admitted = IPDAdmission.objects.filter(status='Admitted').select_related('patient').order_by('-date')
    return render(request, 'ipd/discharge_add.html', {
        'active_sidebar': 'ipd_discharge',
        'today': timezone.localdate().isoformat(),
        'admitted_patients': admitted,
    })


@require_module('discharge', level='view')
def discharge_print(request, pk):
    d = get_object_or_404(
        DischargeSummary.objects.select_related('admission__patient'), pk=pk
    )
    adm = d.admission
    patient = adm.patient

    # Use the canonical billing function to keep all views consistent
    rate_per_day, days_stayed, room_amount = _get_bed_charge_details(adm, d.discharge_date)
    doctor_fees = adm.doctor_fees if adm.doctor_fees else Decimal('0')
    med_total = sum(m.amount for m in adm.medicine_lines.all()) or Decimal('0.00')

    bed_desc = f'Bed / Room Charges (₹{rate_per_day} × {days_stayed} day{"s" if days_stayed != 1 else ""})'
    bill_items = [
        {'desc': bed_desc, 'amount': room_amount},
        {'desc': 'Doctor / Consultation Fees', 'amount': doctor_fees},
    ]
    if med_total:
        bill_items.append({'desc': 'Medicines', 'amount': med_total})

    bill_total = sum(i['amount'] for i in bill_items)
    paid_total = adm.payments.aggregate(s=Sum('amount'))['s'] or Decimal('0.00')
    due_amount = bill_total - paid_total

    return render(request, 'ipd/discharge_print.html', {
        'discharge': d,
        'bill_items': bill_items,
        'bill_total': bill_total,
        'paid_total': paid_total,
        'due_amount': due_amount,
        'days_stayed': days_stayed,
        'rate_per_day': rate_per_day,
        'hospital_name': settings.HOSPITAL_NAME,
        'hospital_address': settings.HOSPITAL_ADDRESS,
        'hospital_phone': settings.HOSPITAL_PHONE,
    })


@require_module('ipd_admission', level='full')
def medicine(request):
    if request.method == 'POST':
        adm = IPDAdmission.objects.filter(
            ipd_no=request.POST.get('ipd_no')
        ).first()

        if adm:
            try:
                qty = max(1, int(request.POST.get('qty') or 1))
                rate = Decimal(request.POST.get('rate') or 0)
                if rate < 0:
                    raise ValueError('Rate cannot be negative.')
                if rate > Decimal('99999.99'):
                    raise ValueError('Rate exceeds maximum allowed value.')
            except (ValueError, Exception) as e:
                messages.error(request, str(e) if str(e) else 'Invalid quantity or rate.')
                return redirect('ipd:medicine')

            with transaction.atomic():
                line = IPDMedicineLine.objects.create(
                    admission=adm,
                    medicine_name=_cap_text(request.POST.get('medicine', '')),
                    quantity=qty,
                    rate=rate,
                )
                if line.amount > 0:
                    LedgerEntry.record_charge(
                        uhid=adm.patient.uhid,
                        tx_type=LedgerEntry.TxType.IPD_BILL,
                        amount=line.amount,
                        payer_type=LedgerEntry.PayerType.PATIENT,
                        description=f'IPD medicine: {line.medicine_name} x{line.quantity} ({adm.ipd_no})',
                        source_app='ipd',
                        source_id=str(line.id),
                        patient=adm.patient,
                        ipd_admission=adm,
                    )
            messages.success(request, 'Medicine added.')
            return redirect('ipd:medicine')

    lines = IPDMedicineLine.objects.select_related('admission').order_by('-id')[:20]
    medicines = [
        {'name': m.medicine_name, 'qty': m.quantity, 'rate': m.rate, 'amount': m.amount}
        for m in lines
    ]
    return render(request, 'ipd/medicine.html', {
        'active_sidebar': 'ipd',
        'medicines': medicines,
    })


@require_module('ipd_list', level='full')
@require_POST
def delete_patient(request, pk):
    admission = get_object_or_404(IPDAdmission, pk=pk)
    with transaction.atomic():
        # Free the bed if occupied by this patient
        bed = Bed.objects.filter(
            room_no=admission.room_no, patient=admission.patient, status='Occupied'
        ).first()
        if bed:
            bed.status = 'Vacant'
            bed.patient = None
            bed.save(update_fields=['status', 'patient'])

        # Reverse all ledger entries tied to this admission
        from income.models import LedgerEntry as _LE, IncomeEntry as _IE
        _LE.objects.filter(ipd_admission=admission).delete()

        # Reverse all IncomeEntry rows posted for this admission
        _IE.objects.filter(
            category='IPD',
            patient_name=admission.patient.name if admission.patient else '',
            description__icontains=admission.ipd_no,
        ).delete()

        admission.delete()

    messages.success(request, 'Patient deleted successfully.')
    return redirect('ipd:patient_list')



@require_module('billing_collect', level='full')
@require_POST
def payment_delete(request, pk):
    """Delete an IPD payment and reverse its ledger entry."""
    payment = get_object_or_404(IPDPayment, pk=pk)
    admission = payment.admission

    with transaction.atomic():
        # Reverse the exact ledger credit row that was created for this payment.
        # We match on source_app + source_id (payment PK) which is set reliably
        # by the payment view. Fall back to amount+admission matching for older
        # rows created before source_id was stamped.
        if admission.patient:
            deleted, _ = LedgerEntry.objects.filter(
                patient=admission.patient,
                ipd_admission=admission,
                source_app='ipd',
                source_id=str(payment.id),
                credit_amount=payment.amount,
            ).delete()

            # Fallback for pre-migration rows without source_id
            if not deleted:
                LedgerEntry.objects.filter(
                    patient=admission.patient,
                    ipd_admission=admission,
                    credit_amount=payment.amount,
                    tx_type=LedgerEntry.TxType.PATIENT_PAYMENT,
                ).order_by('created_at')[:1].delete()

        # Reverse IncomeEntry mirror posted at payment time
        from income.models import IncomeEntry as _IE
        _IE.objects.filter(
            category='IPD',
            patient_name=admission.patient.name if admission.patient else '',
            payment_mode=payment.payment_mode,
            amount=payment.amount,
        ).order_by('-created_at')[:1].delete()

        payment.delete()

    messages.success(request, f'Payment of ₹{payment.amount} deleted.')
    return redirect('ipd:payment')


@require_module('pharmacy', level='full')
@require_POST
def medicine_delete(request, pk):
    """Delete an IPD medicine line and reverse ledger charge."""
    line = get_object_or_404(IPDMedicineLine, pk=pk)
    admission = line.admission
    
    with transaction.atomic():
        # Reverse ledger charge
        if admission.patient:
            LedgerEntry.objects.filter(
                patient=admission.patient,
                source_app='ipd',
                source_id=str(line.id)
            ).delete()
        
        line.delete()
    
    messages.success(request, f'Medicine {line.medicine_name} removed from bill.')
    return redirect('ipd:medicine')
