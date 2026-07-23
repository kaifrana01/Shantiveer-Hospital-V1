from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.db.models import Q, Sum
from django.utils import timezone
from uhid.models import Patient
from income.models import LedgerEntry
from .models import IPDAdmission, IPDPayment, IPDMedicineLine, DischargeSummary
from core.models import Bed
from core.rbac import require_module


def _cap_text(s):
    """Capitalize text: first letter of each word to uppercase, rest lowercase.

    Example: "john smith" -> "John Smith"
    """
    if s is None:
        return ''
    s = str(s).strip()
    return s.title()




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



@require_module('ipd_list', level='view')
def patient_list(request):
    q = request.GET.get('q', '').strip()

    qs = IPDAdmission.objects.select_related('patient').filter(status='Admitted')
    if q:
        qs = qs.filter(
            Q(patient__name__icontains=q)
            | Q(ipd_no__icontains=q)
            | Q(patient__uhid__icontains=q)
        )

    # Pre-compute advance/paid summary in one query.
    qs = qs.annotate(
        advance_paid=Sum('payments__amount')
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

    return render(
        request,
        'ipd/patient_list.html',
        {'active_sidebar': 'ipd', 'patients': patients},
    )


@require_module('ipd_admission', level='full')
def admission(request):
    edit_id = request.GET.get('edit') or request.POST.get('edit_id')

    admission_obj = None
    if edit_id:
        admission_obj = IPDAdmission.objects.select_related('patient').filter(pk=edit_id).first()

    if request.method == 'POST':
        uhid = request.POST.get('uhid')
        patient = Patient.objects.filter(uhid=uhid).first() if uhid else None

        # When editing: update existing admission + patient record if provided.
        if not patient:
            patient = Patient.objects.create(
                name=_cap_text(request.POST.get('patient_name', '')),
                mobile=request.POST.get('contact', ''),
                gender=_cap_text(request.POST.get('gender', 'Male')),
                age_years=int(request.POST.get('age') or 0),
                address=_cap_text(request.POST.get('address', '')),
            )


        if admission_obj:

            # update patient
            if request.POST.get('patient_name') is not None:
                patient.name = _cap_text(request.POST.get('patient_name', ''))
                patient.mobile = request.POST.get('contact', '')
                patient.gender = _cap_text(request.POST.get('gender', 'Male'))
                patient.age_years = int(request.POST.get('age') or 0)
                patient.address = _cap_text(request.POST.get('address', ''))

                patient.save()

            # update admission
            admission_obj.patient = patient
            admission_obj.date = request.POST.get('date') or timezone.localdate()
            admission_obj.time = request.POST.get('time') or None
            admission_obj.guardian = _cap_text(request.POST.get('guardian', ''))
            admission_obj.category = _cap_text(request.POST.get('category', 'General'))
            admission_obj.consultant = _cap_text(request.POST.get('consultant', ''))

            admission_obj.kyc_type = request.POST.get('kyc_type', '')
            admission_obj.kyc_no = request.POST.get('kyc_no', '')
            admission_obj.room_category = request.POST.get('room_category', '')
            admission_obj.room_no = request.POST.get('room_no', '')
            admission_obj.diagnosis = _cap_text(request.POST.get('diagnosis', ''))
            admission_obj.tpa = _cap_text(request.POST.get('tpa', ''))
            admission_obj.policy_no = _cap_text(request.POST.get('policy_no', ''))
            admission_obj.insurance_co = _cap_text(request.POST.get('insurance', ''))
            admission_obj.referral = _cap_text(request.POST.get('referral', ''))

            admission_obj.status = request.POST.get('status', 'Admitted')
            admission_obj.save()
            messages.success(request, 'IPD admission updated.')
        else:
            IPDAdmission.objects.create(
                patient=patient,
                date=request.POST.get('date') or timezone.localdate(),
                time=request.POST.get('time') or None,
                guardian=_cap_text(request.POST.get('guardian', '')),
                category=_cap_text(request.POST.get('category', 'General')),
                consultant=_cap_text(request.POST.get('consultant', '')),

                kyc_type=request.POST.get('kyc_type', ''),
                kyc_no=_cap_text(request.POST.get('kyc_no', '')),
                room_category=_cap_text(request.POST.get('room_category', '')),
                room_no=_cap_text(request.POST.get('room_no', '')),
                diagnosis=_cap_text(request.POST.get('diagnosis', '')),
                tpa=_cap_text(request.POST.get('tpa', '')),
                policy_no=_cap_text(request.POST.get('policy_no', '')),
                insurance_co=_cap_text(request.POST.get('insurance', '')),
                referral=_cap_text(request.POST.get('referral', '')),

                status=request.POST.get('status', 'Admitted'),
            )
            messages.success(request, 'IPD admission saved.')

        # Map Emergency/ICU inputs to ICU before bed allocation + before saving alerts.
        try:
            raw_cat = (request.POST.get('category') or '').strip()
            norm = raw_cat.lower()
            if admission_obj and norm:
                if norm in {'icu', 'emergency', 'emerg', 'er', 'emergency/icu'}:
                    admission_obj.category = 'ICU'
        except Exception:
            pass



        # Auto-allocate a vacant bed when admitting
        room_no = admission_obj.room_no if admission_obj else (request.POST.get('room_no') or '').strip()
        if room_no and admission_obj and admission_obj.status == 'Admitted':
            vacant_bed = (Bed.objects
                .filter(room_no=room_no, status='Vacant')
                .order_by('bed_no')
                .first())

            if vacant_bed:
                vacant_bed.status = 'Occupied'
                vacant_bed.patient = patient
                vacant_bed.save(update_fields=['status', 'patient'])
            else:
                messages.warning(request, f'No vacant bed available in Room {room_no}.')

        # Ensure category used for billing matches ward type input
        try:
            if admission_obj:
                raw = request.POST.get('room_category', '') or request.POST.get('category', '')
                raw_norm = (raw or '').strip()
                if raw_norm:
                    # Store ward type/category like 'General Ward' etc.
                    admission_obj.category = _cap_text(raw_norm)
                    admission_obj.save(update_fields=['category'])
        except Exception:
            pass

        # Persist category mapping if modified
        if admission_obj and admission_obj.category:
            try:
                admission_obj.save(update_fields=['category'])
            except Exception:
                pass

        # --- Advance payment from admission screen ---
        # IPD patient list uses Sum('payments__amount'), so we must save
        # this advance into IPDPayment (and ledger if applicable).
        try:
            adv_raw = (request.POST.get('advance_payment') or '').strip()
            # Support formats like "1,000" or "1000.50"
            adv_raw = adv_raw.replace(',', '')
            adv = Decimal(adv_raw) if adv_raw else Decimal('0.00')

            if admission_obj and adv > 0:
                # Avoid double-charging when user edits admission: if there
                # is already at least one payment and UI provides 0, we won't
                # create anything. If UI provides advance again, it will add.
                IPDPayment.objects.create(
                    admission=admission_obj,
                    amount=adv,
                    payment_mode='Cash',
                    upi_id='',
                    remarks=f'Advance payment ({admission_obj.ipd_no})',
                )

                # Mirror into patient ledger to keep accounting consistent.
                LedgerEntry.record_payment(
                    uhid=admission_obj.patient.uhid,
                    amount=adv,
                    payer_type=LedgerEntry.PayerType.PATIENT,
                    payment_mode='Cash',
                    description=f'IPD advance payment ({admission_obj.ipd_no})',
                    patient=admission_obj.patient,
                    ipd_admission=admission_obj,
                )
        except Exception:
            # Don't block admission save if advance parsing/ledger fails.
            pass

        return redirect('ipd:patient_list')

    present = IPDAdmission.objects.filter(status='Admitted').select_related('patient')

    present_list = [{'name': a.patient.name, 'room': a.room_no, 'ipd_no': a.ipd_no, 'category': a.category} for a in present]

    from masterdata.models import Doctor
    doctors = Doctor.objects.filter(is_active=True).order_by('name')


    # Pre-fill form when editing.
    ctx = {
        'active_sidebar': 'ipd',
        'today': timezone.localdate().isoformat(),
        'present_patients': present_list,

        'ipd_no': admission_obj.ipd_no if admission_obj else f'IPD{IPDAdmission.objects.count() + 101}',
        'form_ipd_no': admission_obj.ipd_no if admission_obj else '',
        'form_bed_charge': getattr(admission_obj, 'bed_charge', None) if admission_obj else '',


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
        'form_category': admission_obj.category if admission_obj else 'General',
        'form_consultant': admission_obj.consultant if admission_obj else '',
        'form_kyc_type': admission_obj.kyc_type if admission_obj else 'Aadhar',
        'form_kyc_no': admission_obj.kyc_no if admission_obj else '',
        'form_room_category': admission_obj.room_category if admission_obj else '',
'form_room_no': admission_obj.room_no if admission_obj else '',
        
        'doctors': doctors,

        # Bed dropdown options (from Bed Manager)

        # Bed dropdown options (Vacant only)
        # Filter by ward type using room_category.
        'bed_options': (
            (lambda qs: list(qs.order_by('room_no', 'bed_no').values('room_no', 'bed_no')))(
                (
                    (lambda bed_qs, ward_cat_lower: (
                        bed_qs.filter(room_no__istartswith='P') if 'private' in ward_cat_lower else
                        bed_qs.filter(room_no__istartswith='E') if 'emergency' in ward_cat_lower else
                        bed_qs.filter(room_no__istartswith='G')
                    ))
                    (Bed.objects.filter(status='Vacant'), (admission_obj.room_category if admission_obj else request.GET.get('room_category', '')).strip().lower())
                    if (admission_obj.room_category if admission_obj else request.GET.get('room_category', '')).strip().lower() else
                    Bed.objects.filter(status='Vacant').filter(room_no__istartswith='G')
                )
            )
        ),


        'form_diagnosis': admission_obj.diagnosis if admission_obj else '',
        'form_tpa': admission_obj.tpa if admission_obj else '',
        'form_policy_no': admission_obj.policy_no if admission_obj else '',
        'form_insurance': admission_obj.insurance_co if admission_obj else '',
        'form_referral': admission_obj.referral if admission_obj else '',
        'form_status': admission_obj.status if admission_obj else 'Admitted',
    }

    return render(request, 'ipd/admission.html', ctx)



from django.http import JsonResponse


def _compute_ipd_bill_total(adm):
    """Compute total IPD bill based on ward type (category) and medicines.

    Bed Charges/Room Charges + Doctor Fees are mapped from admission.category
    (Ward Type on the admission screen).
    """
    ward = (adm.category or '').strip().lower() if adm else ''

    ward_map = {
        'general ward': (Decimal('2500'), Decimal('2000')),
        'private ward': (Decimal('3500'), Decimal('2500')),
        'emergency ward': (Decimal('2000'), Decimal('2200')),
        'icu': (Decimal('4000'), Decimal('3000')),
    }

    # Fallback to existing defaults
    room_amount, doctor_fees = ward_map.get(ward, (Decimal('1500'), Decimal('500')))

    med_total = sum(m.amount for m in adm.medicine_lines.all()) or Decimal('0.00')
    return room_amount + doctor_fees + med_total


@require_module('billing_collect', level='view')
def payment_total(request):
    ipd_no = (request.GET.get('ipd_no') or '').strip().upper()
    if ipd_no and not ipd_no.startswith('IPD'):
        ipd_no = f'IPD{ipd_no}'

    adm = IPDAdmission.objects.select_related('patient').filter(ipd_no=ipd_no).first()
    total = _compute_ipd_bill_total(adm) if adm else Decimal('0.00')
    # Provide patient name to support auto-fill on the payment page.
    patient_name = adm.patient.name if adm else ''
    return JsonResponse({'total': str(total), 'patient_name': patient_name})


@require_module('billing_collect', level='full')
def payment(request):
    """IPD payment screen.

    Important: this view must NOT navigate/open any IPD patient context based
    on query-string parameters. The payment page is always rendered as-is.
    """
    # Ignore any query params (e.g., ipd_no) for safety; they are only used by
    # the AJAX endpoint /ipd/payment/total/.
    request.GET = request.GET.copy()
    request.GET.clear()

    if request.method == 'POST':
        adm = IPDAdmission.objects.filter(ipd_no=request.POST.get('ipd_no')).first()
        if adm:
            amount = Decimal(request.POST.get('amount') or 0)
            mode = request.POST.get('mode', 'Cash')
            remarks = _cap_text(request.POST.get('remarks', ''))

            upi_id = ''
            if mode == 'UPI':
                upi_id = (request.POST.get('upi_id') or '').strip()

            IPDPayment.objects.create(
                admission=adm,
                amount=amount,
                payment_mode=mode,
                upi_id=upi_id,
                remarks=remarks,
            )


            # Mirror into the single patient ledger (Phase 2/3 architecture).
            # Desk collections from the IPD payment screen are always
            # against the PATIENT side of the ledger; insurance-side
            # postings happen via the dedicated TPA settlement workflow
            # (LedgerEntry.settle_insurance_claim).
            LedgerEntry.record_payment(
                uhid=adm.patient.uhid,
                amount=amount,
                payer_type=LedgerEntry.PayerType.PATIENT,
                payment_mode=mode,
                description=remarks or f'IPD payment for {adm.ipd_no}',
                patient=adm.patient,
                ipd_admission=adm,
            )
            messages.success(request, 'Payment recorded.')
            # After saving payment, redirect to the IPD bill page for the same admission
            # so the user can immediately see updated balance.
            from django.urls import reverse
            return redirect(f"{reverse('ipd:bill')}?ipd_no={adm.ipd_no}")

    payments = IPDPayment.objects.select_related('admission__patient').order_by('-paid_at')[:20]

    data = [{'ipd_no': p.admission.ipd_no, 'name': p.admission.patient.name, 'amount': p.amount, 'mode': p.payment_mode, 'date': p.paid_at.date()} for p in payments]
    return render(request, 'ipd/payment.html', {'active_sidebar': 'ipd', 'payments': data})


@require_module('patient_bill', level='view')
def bill(request):
    bill_data = None
    ipd_no = request.GET.get('ipd_no')

    if ipd_no:
        # Accept input like `ipd123`, `IPD123`, or `123` and match consistently.
        ipd_no_norm = ipd_no.strip().upper()
        if ipd_no_norm and not ipd_no_norm.startswith('IPD'):
            ipd_no_norm = f'IPD{ipd_no_norm}'

        adm = IPDAdmission.objects.select_related('patient').filter(ipd_no=ipd_no_norm).first()

        if adm:
            # Bill line items
            # Room/Bed charge should vary as per admission.bed_charge
            # (set from Bed Charges input on IPD admission screen).
            room_amount = getattr(adm, 'bed_charge', None) or Decimal('0.00')
            doctor_fees = Decimal('2000')
            med_total = sum(m.amount for m in adm.medicine_lines.all()) or Decimal('0.00')

            items = [
                {'desc': 'Bed Charges', 'amount': room_amount},
                {'desc': 'Doctor Fees', 'amount': doctor_fees},
            ]
            if med_total:
                items.append({'desc': 'Medicines', 'amount': med_total})

            total = sum((i['amount'] for i in items), Decimal('0.00'))


            # Post charges to income ledger automatically
            # (This mirrors what ipd:medicine does, but for the whole IPD bill.)
            LedgerEntry.record_charge(
                uhid=adm.patient.uhid,
                tx_type=LedgerEntry.TxType.IPD_BILL,
                amount=room_amount,
                payer_type=LedgerEntry.PayerType.PATIENT,
                description=f'IPD Room Charges ({adm.ipd_no})',
                source_app='ipd',
                source_id=str(adm.id),
                patient=adm.patient,
                ipd_admission=adm,
            )
            LedgerEntry.record_charge(
                uhid=adm.patient.uhid,
                tx_type=LedgerEntry.TxType.IPD_BILL,
                amount=doctor_fees,
                payer_type=LedgerEntry.PayerType.PATIENT,
                description=f'IPD Doctor Fees ({adm.ipd_no})',
                source_app='ipd',
                source_id=str(adm.id),
                patient=adm.patient,
                ipd_admission=adm,
            )
            if med_total:
                LedgerEntry.record_charge(
                    uhid=adm.patient.uhid,
                    tx_type=LedgerEntry.TxType.IPD_BILL,
                    amount=med_total,
                    payer_type=LedgerEntry.PayerType.PATIENT,
                    description=f'IPD Medicines Total ({adm.ipd_no})',
                    source_app='ipd',
                    source_id=str(adm.id),
                    patient=adm.patient,
                    ipd_admission=adm,
                )

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
                'items': [{'desc': i['desc'], 'amount': i['amount']} for i in items],
                'total': total,
                'paid_total': paid_total,
                'due_amount': due_amount,
            }

    return render(request, 'ipd/bill.html', {'active_sidebar': 'ipd', 'bill': bill_data})



@require_module('ipd_admission', level='view')
def admission_beds(request):
    ward = (request.GET.get('ward') or '').strip().lower()
    if not ward:
        return JsonResponse({'beds': []})

    if 'private' in ward:
        prefix = 'P'
    elif 'emergency' in ward:
        prefix = 'E'
    else:
        prefix = 'G'

    beds_qs = Bed.objects.filter(status='Vacant', room_no__istartswith=prefix).order_by('room_no', 'bed_no')
    beds = list(beds_qs.values('room_no', 'bed_no'))
    return JsonResponse({'beds': beds})


@require_module('discharge', level='view')
def discharge_list(request):
    q = request.GET.get('q', '').strip()
    items = DischargeSummary.objects.select_related('admission__patient')
    if q:
        items = items.filter(Q(admission__ipd_no__icontains=q) | Q(admission__patient__name__icontains=q))
    discharges = [{
        'id': d.id, 'ipd_no': d.admission.ipd_no, 'name': d.admission.patient.name,
        'age': d.admission.patient.age_years, 'gender': d.admission.patient.gender,
        'guardian': d.admission.guardian, 'room': d.admission.room_no,
        'contact': d.admission.patient.mobile, 'consultant': d.admission.consultant,
        'discharge_date': str(d.discharge_date),
    } for d in items]
    return render(request, 'ipd/discharge_list.html', {'active_sidebar': 'ipd', 'discharges': discharges, 'q': q})


@require_module('discharge', level='full')
def discharge_add(request):
    if request.method == 'POST':
        adm = IPDAdmission.objects.filter(ipd_no=request.POST.get('ipd_no')).first()
        if adm:
            DischargeSummary.objects.get_or_create(
                admission=adm,
                defaults={'discharge_date': request.POST.get('discharge_date') or timezone.localdate()},
            )
            adm.status = 'Discharged'
            adm.save()

            # Free up the bed that was occupied by this patient.
            bed = Bed.objects.filter(room_no=adm.room_no, patient=adm.patient, status='Occupied').first()
            if bed:
                bed.status = 'Vacant'
                bed.patient = None
                bed.save(update_fields=['status', 'patient'])

            messages.success(request, 'Discharge added.')

            # If UI provided a next URL (e.g., payment page), redirect there.
            next_url = (request.POST.get('next') or '').strip()
            if next_url:
                return redirect(next_url)

        return redirect('ipd:discharge_list')
    return redirect('ipd:discharge_list')


@require_module('discharge', level='view')
def discharge_print(request, pk):
    d = get_object_or_404(DischargeSummary.objects.select_related('admission__patient'), pk=pk)
    return render(request, 'prescription/print.html', {
        'record': {'name': d.admission.patient.name, 'opd_no': d.admission.ipd_no, 'date': str(d.discharge_date), 'diagnosis': d.admission.diagnosis, 'medicines': 'Follow up in 7 days', 'advice': d.notes},
    })


@require_module('pharmacy', level='view')
def medicine(request):
    if request.method == 'POST':
        adm = IPDAdmission.objects.filter(
            ipd_no=request.POST.get('ipd_no')
        ).first()

        if adm:
            line = IPDMedicineLine.objects.create(
                admission=adm,
                medicine_name=_cap_text(request.POST.get('medicine', '')),

                quantity=int(request.POST.get('qty') or 1),
                rate=Decimal(request.POST.get('rate') or 0),
            )
            if line.amount > 0:
                # Medicine dispensed during an IPD stay is a charge
                # against the patient's stay, not something collected on
                # the spot — unlike OPD/Lab/Pharmacy counter sales, this
                # is just a DEBIT. It adds to the outstanding balance
                # until settled at discharge via ipd:payment.
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

    lines = IPDMedicineLine.objects.select_related(
        'admission'
    ).order_by('-id')[:20]

    medicines = [
        {
            'name': m.medicine_name,
            'qty': m.quantity,
            'rate': m.rate,
            'amount': m.amount
        }
        for m in lines
    ]

    return render(
        request,
        'ipd/medicine.html',
        {
            'active_sidebar': 'ipd',
            'medicines': medicines
        }
    )


@require_module('ipd_list', level='full')
def delete_patient(request, pk):
    admission = get_object_or_404(IPDAdmission, pk=pk)

    if request.method == "POST":
        admission.delete()
        messages.success(
            request,
            "Patient deleted successfully."
        )

    return redirect('ipd:patient_list')