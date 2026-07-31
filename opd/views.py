from decimal import Decimal
from django.db import transaction
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.views.decorators.http import require_POST

from uhid.models import Patient
from income.models import LedgerEntry

from .models import OPDVisit, OPDVisitTestItem
from prescription.models import Prescription
from lab.models import LabTestMaster
from core.rbac import require_module, has_access
from masterdata.models import Doctor


def _post_opd_visit_to_ledger(visit):
    """Mirror an OPD visit into the central patient ledger and income daybook."""
    if visit.total_amount <= 0:
        return

    LedgerEntry.record_charge(
        uhid=visit.patient.uhid,
        tx_type=LedgerEntry.TxType.OPD_BILL,
        amount=visit.total_amount,
        payer_type=LedgerEntry.PayerType.PATIENT,
        description=f'OPD visit {visit.opd_no} ({visit.head})',
        source_app='opd',
        source_id=visit.opd_no,
        patient=visit.patient,
    )
    LedgerEntry.record_payment(
        uhid=visit.patient.uhid,
        amount=visit.total_amount,
        payer_type=LedgerEntry.PayerType.PATIENT,
        payment_mode=visit.payment_mode,
        description=f'OPD visit {visit.opd_no} payment collected at registration',
        source_app='opd',
        source_id=visit.opd_no,
        patient=visit.patient,
    )
    # Mirror into IncomeEntry so daybook reflects OPD collections
    from income.models import IncomeEntry
    IncomeEntry.objects.create(
        date=visit.date,
        category='OPD',
        patient_name=visit.patient.name,
        description=f'OPD visit {visit.opd_no} ({visit.head})',
        payment_mode=visit.payment_mode,
        amount=visit.total_amount,
    )


@require_module('opd_registration', level='view')
def registration(request):
    now = timezone.localtime()
    edit_id = request.GET.get('edit')

    # Optional: auto-fill by OPD No
    search_opd_no = (request.GET.get('opd_no') or '').strip().upper()
    initial = {}
    if search_opd_no:
        try:
            visit = OPDVisit.objects.select_related('patient').filter(opd_no=search_opd_no).first()
            if visit:
                initial = {'patient': visit.patient, 'visit': visit}
            else:
                messages.error(request, f'OPD {search_opd_no} not found.')
        except Exception:
            messages.error(request, 'Unable to fetch OPD details.')

    if request.method == 'POST':
        uhid = request.POST.get('uhid', '').strip()

        # Block write operations for view-only roles (e.g. Doctor on OPD)
        if request.is_view_only:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("Your role has view-only access to OPD registration.")

        # If this is an edit, update existing visit instead of creating a new one.
        edit_id = request.GET.get('edit')
        visit_obj = None
        if edit_id:
            visit_obj = get_object_or_404(OPDVisit, pk=edit_id)
            if not has_access(request.user, 'opd_registration', level='full'):
                raise PermissionDenied
        else:
            if not has_access(request.user, 'opd_registration', level='full'):
                raise PermissionDenied

        def _cap_text(s):
            if s is None:
                return ''
            s = str(s).strip()
            return s.title()

        if uhid:
            patient, _ = Patient.objects.get_or_create(
                uhid=uhid,
                defaults={
                    'name': _cap_text(request.POST.get('patient_name', '')),
                    'mobile': request.POST.get('phone', ''),
                    'gender': request.POST.get('gender', 'Male'),
                    'address': _cap_text(request.POST.get('address', '')),
                },
            )
        else:
            # BUG-17 FIX: wrap age parsing in try/except so a non-numeric
            # value (e.g. "abc" or empty string) doesn't crash with ValueError.
            try:
                age_val = int(request.POST.get('age') or 0)
            except (ValueError, TypeError):
                age_val = 0
            patient = Patient.objects.create(
                name=_cap_text(request.POST.get('patient_name', '')),
                mobile=request.POST.get('phone', ''),
                gender=request.POST.get('gender', 'Male'),
                address=_cap_text(request.POST.get('address', '')),
                age_years=age_val,
            )

        # Update patient fields
        patient.name = _cap_text(request.POST.get('patient_name', patient.name))
        patient.mobile = request.POST.get('phone', patient.mobile)
        patient.gender = request.POST.get('gender', patient.gender)
        patient.address = _cap_text(request.POST.get('address', patient.address))
        if request.POST.get('age'):
            try:
                patient.age_years = int(request.POST.get('age'))
            except (ValueError, TypeError):
                pass
        patient.save()

        # Basic visit fields
        date_val = request.POST.get('date') or now.date()
        time_val = request.POST.get('time') or now.time()
        doctor_raw = request.POST.get('doctor') or request.POST.get('doctor_other') or ''

        fees_val = Decimal(request.POST.get('fees') or 0)
        discount_val = Decimal(request.POST.get('discount') or 0)
        head_val = request.POST.get('head', 'Opd Consultation')
        payment_mode_val = request.POST.get('payment_mode', 'Cash')
        reference_val = request.POST.get('reference', '')
        upi_val = (request.POST.get('upi_id') or '').strip()

        # Parse selected tests + qty
        selected_test_ids = request.POST.getlist('tests') or []
        test_ids_int = []
        for tid in selected_test_ids:
            try:
                test_ids_int.append(int(tid))
            except Exception:
                pass

        qty_map = {}
        for tid in test_ids_int:
            qty_raw = request.POST.get(f'test_qty_{tid}', '')
            try:
                qty_map[tid] = max(1, int(qty_raw)) if qty_raw != '' else 1
            except Exception:
                qty_map[tid] = 1

        with transaction.atomic():
            if visit_obj:
                # Update existing visit
                visit_obj.patient = patient
                visit_obj.date = date_val
                visit_obj.time = time_val
                visit_obj.referral = _cap_text(request.POST.get('referral', ''))
                visit_obj.doctor_name = _cap_text(doctor_raw)

                visit_obj.fees = fees_val
                visit_obj.discount = discount_val
                visit_obj.head = head_val
                visit_obj.payment_mode = payment_mode_val
                visit_obj.reference_info = reference_val
                visit_obj.upi_id = upi_val

                # Replace test items
                visit_obj.test_items.all().delete()

                total_tests = Decimal('0')
                tests = LabTestMaster.objects.filter(id__in=test_ids_int, is_active=True)
                for t in tests:
                    qty = qty_map.get(t.id, 1)
                    line = OPDVisitTestItem(
                        opd_visit=visit_obj,
                        test=t,
                        rate=t.rate,
                        quantity=qty,
                    )
                    line.save()
                    total_tests += line.amount

                visit_obj.total_amount = max(0, (fees_val - discount_val) + total_tests)
                visit_obj.save()

                Prescription.objects.get_or_create(opd_visit=visit_obj)

                # BUG-02 FIX: when a visit is edited and the total amount
                # has changed, reverse the old IncomeEntry and post a new
                # one so the daybook stays accurate.  We don't touch
                # LedgerEntry here because OPD posts charge+payment
                # simultaneously (balance is always 0), so a net-zero
                # adjustment is only needed if the amount actually changed.
                # We do a simple replace: delete old + create new.
                from income.models import IncomeEntry as _IE
                old_entry = _IE.objects.filter(
                    category='OPD',
                    description__icontains=visit_obj.opd_no,
                ).order_by('-created_at').first()

                old_amount = old_entry.amount if old_entry else None
                if old_entry:
                    old_entry.delete()

                # Always (re)create the IncomeEntry so edits on visits that
                # pre-date this fix also get a correct daybook entry.
                if visit_obj.total_amount > 0:
                    _IE.objects.create(
                        date=visit_obj.date,
                        category='OPD',
                        patient_name=visit_obj.patient.name,
                        description=f'OPD visit {visit_obj.opd_no} ({visit_obj.head}) [edited]',
                        payment_mode=visit_obj.payment_mode,
                        amount=visit_obj.total_amount,
                    )
                    # Update LedgerEntry only if amount actually changed
                    if old_amount is not None and old_amount != visit_obj.total_amount:
                        from income.models import LedgerEntry as _LE
                        _LE.objects.filter(
                            source_app='opd',
                            source_id=visit_obj.opd_no,
                        ).delete()
                        _LE.record_charge(
                            uhid=visit_obj.patient.uhid,
                            tx_type=_LE.TxType.OPD_BILL,
                            amount=visit_obj.total_amount,
                            payer_type=_LE.PayerType.PATIENT,
                            description=f'OPD visit {visit_obj.opd_no} ({visit_obj.head}) [edited]',
                            source_app='opd',
                            source_id=visit_obj.opd_no,
                            patient=visit_obj.patient,
                        )
                        _LE.record_payment(
                            uhid=visit_obj.patient.uhid,
                            amount=visit_obj.total_amount,
                            payer_type=_LE.PayerType.PATIENT,
                            payment_mode=visit_obj.payment_mode,
                            description=f'OPD visit {visit_obj.opd_no} payment [edited]',
                            source_app='opd',
                            source_id=visit_obj.opd_no,
                            patient=visit_obj.patient,
                        )

                messages.success(request, f'OPD {visit_obj.opd_no} updated successfully.')
            else:
                # Create new visit
                visit_obj = OPDVisit.objects.create(
                    patient=patient,
                    date=date_val,
                    time=time_val,
                    referral=_cap_text(request.POST.get('referral', '')),
                    doctor_name=_cap_text(doctor_raw),
                    fees=fees_val,
                    discount=discount_val,
                    head=head_val,
                    payment_mode=payment_mode_val,
                    upi_id=upi_val,
                    reference_info=reference_val,
                    total_amount=Decimal('0'),
                )

                total_tests = Decimal('0')
                tests = LabTestMaster.objects.filter(id__in=test_ids_int, is_active=True)
                for t in tests:
                    qty = qty_map.get(t.id, 1)
                    line = OPDVisitTestItem(
                        opd_visit=visit_obj,
                        test=t,
                        rate=t.rate,
                        quantity=qty,
                    )
                    line.save()
                    total_tests += line.amount

                visit_obj.total_amount = max(0, (fees_val - discount_val) + total_tests)
                visit_obj.save()

                Prescription.objects.get_or_create(opd_visit=visit_obj)
                # Post ledger + income inside the same atomic block as the visit
                _post_opd_visit_to_ledger(visit_obj)
                messages.success(request, f'OPD {visit_obj.opd_no} saved successfully.')

        # Redirect to opd_list if available, otherwise prescription:list
        if has_access(request.user, 'opd_list'):
            return redirect('opd:patient_list')
        return redirect('prescription:list')

    # BUG-05 FIX: use the same max-based logic as OPDVisit.save() so the
    # preview number shown to the user matches what will actually be assigned.
    # Using .count() was wrong when visits are deleted — the count resets and
    # the displayed number collides with existing OPD numbers.
    _numeric_nos = (
        OPDVisit.objects
        .filter(opd_no__regex=r'^OPD\d+$')
        .values_list('opd_no', flat=True)
    )
    _max_n = max(
        (int(no[3:]) for no in _numeric_nos if no[3:].isdigit()),
        default=0,
    )
    next_no = f'OPD{_max_n + 1:03d}'

    if edit_id:
        v = get_object_or_404(OPDVisit, pk=edit_id)
        initial = {'patient': v.patient, 'visit': v}

    doctors = Doctor.objects.filter(is_active=True).order_by('name')
    return render(request, 'opd/registration.html', {
        'active_sidebar': 'opd',
        'opd_no': next_no,
        'today': now.date().isoformat(),
        'now_time': now.strftime('%H:%M'),
        'initial': initial,
        'lab_tests': LabTestMaster.objects.filter(is_active=True).order_by('name'),
        'doctors': doctors,
    })


@require_module('opd_registration', level='full')
@require_POST
def delete_opd_visit(request, pk):
    visit = get_object_or_404(OPDVisit, pk=pk)
    with transaction.atomic():
        if visit.total_amount > 0:
            # Post a compensating credit so the patient ledger stays balanced
            try:
                LedgerEntry.objects.create(
                    uhid=visit.patient.uhid,
                    patient=visit.patient,
                    tx_type=LedgerEntry.TxType.ADJUSTMENT,
                    payer_type=LedgerEntry.PayerType.PATIENT,
                    credit_amount=visit.total_amount,
                    description=f'OPD visit {visit.opd_no} voided/deleted',
                    source_app='opd',
                    source_id=visit.opd_no,
                )
            except Exception:
                pass
            # Reverse the IncomeEntry posted at registration time
            from income.models import IncomeEntry
            IncomeEntry.objects.filter(
                category='OPD',
                description__icontains=visit.opd_no,
            ).order_by('-created_at')[:1].delete()
        visit.delete()
    messages.success(request, f'OPD {visit.opd_no} deleted successfully.')
    if has_access(request.user, 'opd_list'):
        return redirect('opd:patient_list')
    return redirect('prescription:list')



@require_module('opd_list', level='view')
def patient_list(request):
    """OPD patient list — accessible to Receptionist (FULL) and Doctor (FULL)
    without requiring prescription module access."""
    q = (request.GET.get('q') or '').strip()
    referral = (request.GET.get('referral') or '').strip()

    visits = OPDVisit.objects.select_related('patient').order_by('-date', '-time')
    if q:
        visits = visits.filter(
            Q(opd_no__icontains=q) |
            Q(patient__name__icontains=q) |
            Q(patient__uhid__icontains=q) |
            Q(patient__mobile__icontains=q)
        )
    if referral:
        visits = visits.filter(referral__icontains=referral)

    referral_doctors = (
        OPDVisit.objects.exclude(referral='')
        .values_list('referral', flat=True)
        .distinct()
        .order_by('referral')
    )

    from core.services import opd_to_dict
    records = [opd_to_dict(v) for v in visits[:200]]

    return render(request, 'opd/patient_list.html', {
        'active_sidebar': 'opd',
        'records': records,
        'q': q,
        'referral_doctors': referral_doctors,
        'selected_referral': referral,
    })
