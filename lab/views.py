from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.views.decorators.http import require_POST

from uhid.models import Patient

from income.models import LedgerEntry, IncomeEntry, validate_payment_amount, validate_payment_mode

from .models import (
    LabTestMaster,
    LabInvestigation,
    LabInvestigationItem,
    LabTestResult,
)
from core.rbac import require_module


from django.http import JsonResponse


def _lab_due(inv):
    """Compute outstanding due for a specific lab investigation.
    Lab bills are collected in full at billing time so this is normally 0.00.
    Returns a formatted string.
    """
    try:
        from django.db.models import Sum as _Sum
        qs = LedgerEntry.objects.filter(
            source_app='lab',
            source_id=inv.bill_no,
        )
        agg = qs.aggregate(
            total_debit=_Sum('debit_amount'),
            total_credit=_Sum('credit_amount'),
        )
        debit = agg['total_debit'] or Decimal('0')
        credit = agg['total_credit'] or Decimal('0')
        balance = debit - credit
        return f'{balance:.2f}'
    except Exception:
        return '--'



@require_module('lab', level='full')
def investigation(request):
    if request.method == 'POST':
        patient = None
        uhid = request.POST.get('uhid')
        if uhid:
            patient = Patient.objects.filter(uhid=uhid).first()

        patient_name = (request.POST.get('patient_name') or '').strip()
        selected_tests = request.POST.getlist('tests')

        if not selected_tests:
            messages.error(request, 'Please select at least one lab test before submitting.')
            return render(request, 'lab/investigation.html', {
                'active_sidebar': 'lab',
                'tests': LabTestMaster.objects.filter(is_active=True),
                'today': timezone.localdate().isoformat(),
                'hospital_upi_id': settings.HOSPITAL_UPI_ID,
            })

        if not patient_name:
            messages.error(request, 'Patient Name is required to submit Lab Investigation.')
            return render(request, 'lab/investigation.html', {
                'active_sidebar': 'lab',
                'tests': LabTestMaster.objects.filter(is_active=True),
                'today': timezone.localdate().isoformat(),
                'hospital_upi_id': settings.HOSPITAL_UPI_ID,
            })

        with transaction.atomic():
            # Validate and sanitise payment fields before creating any records
            raw_discount = request.POST.get('discount') or '0'
            try:
                discount_val = Decimal(raw_discount)
                if discount_val < 0:
                    discount_val = Decimal('0')
            except Exception:
                discount_val = Decimal('0')

            raw_mode = request.POST.get('payment_mode', 'Cash')
            try:
                payment_mode_val = validate_payment_mode(raw_mode, allowed=['Cash', 'UPI', 'Card'])
            except ValueError:
                payment_mode_val = 'Cash'

            inv = LabInvestigation.objects.create(
                patient=patient,
                patient_name=patient_name,
                mobile=request.POST.get('mobile', ''),
                address=request.POST.get('address', ''),
                consultant=request.POST.get('consultant', '-- Self --'),
                referred_by=request.POST.get('referred', 'SELF'),
                remarks=request.POST.get('remarks', ''),
                discount=discount_val,
                payment_mode=payment_mode_val,
                test_date=request.POST.get('date') or timezone.localdate(),
            )

            # Defensive de-duplication:
            # The UI/POST may contain repeated test IDs (e.g. CBC, KFT, CBC, KFT)
            # even when the user clicks only once.
            # We convert posted tests -> {test_id: summed_quantity} and create
            # exactly one LabInvestigationItem per test_id.
            posted_test_ids = request.POST.getlist('tests')
            qty_by_test_id = {}

            for test_id in posted_test_ids:
                try:
                    qty = int(request.POST.get(f'qty_{test_id}', 1))
                except (TypeError, ValueError):
                    qty = 1
            
                # Sum quantities for duplicate tests (e.g., if CBC appears twice with qty 1 and 2, sum to 3)
                if str(test_id) in qty_by_test_id:
                    qty_by_test_id[str(test_id)] += qty
                else:
                    qty_by_test_id[str(test_id)] = qty

            total = Decimal(0)
            for test_id, qty in qty_by_test_id.items():
                test = LabTestMaster.objects.filter(pk=test_id).first()
                if not test:
                    continue

                item, _created = LabInvestigationItem.objects.update_or_create(
                    investigation=inv,
                    test=test,
                    defaults={
                        'rate': test.rate,
                        'quantity': qty,
                    },
                )
                total += item.amount

            inv.total = total - inv.discount
            inv.save()

            from income.models import IncomeEntry
            IncomeEntry.objects.create(
                date=inv.test_date, category='Investigation', patient_name=inv.patient_name,
                description=f'Lab Bill {inv.bill_no}', payment_mode=inv.payment_mode, amount=inv.total,
            )

            # Mirror into the central patient ledger (Phase 2/3), same as
            # OPD/IPD. Like OPD, lab fees are collected in full at billing
            # time, so this is a charge immediately followed by an equal
            # payment. Only possible when the bill is actually tied to a
            # known UHID — walk-in lab bills with no Patient match (patient
            # stayed None above) have nothing to post against.
            if patient and inv.total > 0:
                LedgerEntry.record_charge(
                    uhid=patient.uhid,
                    tx_type=LedgerEntry.TxType.LAB_BILL,
                    amount=inv.total,
                    payer_type=LedgerEntry.PayerType.PATIENT,
                    description=f'Lab bill {inv.bill_no}',
                    source_app='lab',
                    source_id=inv.bill_no,
                    patient=patient,
                )
                LedgerEntry.record_payment(
                    uhid=patient.uhid,
                    amount=inv.total,
                    payer_type=LedgerEntry.PayerType.PATIENT,
                    payment_mode=inv.payment_mode,
                    description=f'Lab bill {inv.bill_no} payment collected at billing',
                    source_app='lab',
                    source_id=inv.bill_no,
                    patient=patient,
                )

        messages.success(request, f'Lab bill {inv.bill_no} submitted.')
        return redirect('lab:view_all')

    return render(request, 'lab/investigation.html', {
        'active_sidebar': 'lab',
        'tests': LabTestMaster.objects.filter(is_active=True),
        'today': timezone.localdate().isoformat(),
        'hospital_upi_id': settings.HOSPITAL_UPI_ID,
    })


@require_module('lab', level='view')
def view_all(request):
    # /lab/view-all/ should show the same UI as “Lab Patient List”.
    return patient_list(request)





@require_module('lab', level='view')
def view_report(request, pk):
    inv = get_object_or_404(LabInvestigation.objects.prefetch_related('items__test', 'items__results'), pk=pk)
    test_results = []
    for item in inv.items.all():
        result_obj = item.results.first()
        test_results.append({
            'item_id': item.id,
            'name': item.test.name,
            'qty': item.quantity,
            'rate': item.rate,
            'amount': item.amount,
            'result': result_obj.result_value if result_obj else '',
            'unit': result_obj.unit if result_obj else '',
            'ref': result_obj.reference_range if result_obj else '',
            'has_result': result_obj is not None,
        })
    report = {
        'id': inv.id,
        'bill_no': inv.bill_no,
        'patient': inv.patient_name,
        'mobile': inv.mobile,
        'address': inv.address,
        'consultant': inv.consultant,
        'referred_by': inv.referred_by,
        'remarks': inv.remarks,
        'date': str(inv.test_date),
        'total': inv.total,
        'discount': inv.discount,
        'payment_mode': inv.payment_mode,
        'test_results': test_results,
    }
    return render(request, 'lab/view_report.html', {'active_sidebar': 'lab', 'report': report, 'inv': inv})





@require_module('lab', level='view')
def patient_list(request):

    q = (request.GET.get('q') or '').strip()
    referral = (request.GET.get('referral') or '').strip()

    qs = LabInvestigation.objects.select_related('patient').prefetch_related('items__test').order_by('-created_at')
    if q:
        qs = qs.filter(
            Q(bill_no__icontains=q) |
            Q(patient_name__icontains=q) |
            Q(patient__uhid__icontains=q)
        )
    if referral:
        qs = qs.filter(referred_by__icontains=referral)

    # Distinct referral doctors for filter dropdown
    referral_doctors = (
        LabInvestigation.objects.exclude(referred_by='')
        .exclude(referred_by='SELF')
        .values_list('referred_by', flat=True)
        .distinct()
        .order_by('referred_by')
    )

    # Build rows for template
    inv_list = list(qs[:100])

    # ── Batch-load ledger dues in ONE query instead of one per row ──────
    bill_nos = [inv.bill_no for inv in inv_list]
    due_map = {}  # bill_no → formatted balance string
    try:
        from income.models import LedgerEntry
        from django.db.models import Sum as _Sum
        ledger_rows = (
            LedgerEntry.objects
            .filter(source_app='lab', source_id__in=bill_nos)
            .values('source_id')
            .annotate(
                total_debit=_Sum('debit_amount'),
                total_credit=_Sum('credit_amount'),
            )
        )
        for row in ledger_rows:
            bal = (row['total_debit'] or 0) - (row['total_credit'] or 0)
            due_map[row['source_id']] = f'{bal:.2f}' if bal != 0 else '0.00'
    except Exception:
        pass

    rows = []
    for inv in inv_list:
        patient = getattr(inv, 'patient', None)
        rows.append({
            'id': inv.id,
            'name': inv.patient_name,
            'date': str(inv.test_date),
            'time': inv.created_at.strftime('%H:%M') if inv.created_at else '',
            'tests': ', '.join(i.test.name for i in inv.items.all()),
            'bill_no': inv.bill_no,
            'age': getattr(patient, 'age_display', '') if patient else '',
            'consultant': inv.consultant,
            'referred_by': inv.referred_by,
            'amount': inv.total if inv.total is not None else '--',
            'due': due_map.get(inv.bill_no, '0.00'),
            'ayushman_card_no': getattr(inv, 'ayushman_card_no', None) or '--',
            'id_proof': getattr(inv, 'id_proof', None) or '--',
        })


    return render(request, 'lab/patient_list.html', {
        'active_sidebar': 'lab',
        'reports': rows,
        'q': q,
        'referral_doctors': referral_doctors,
        'selected_referral': referral,
    })


@require_module('lab', level='view')
def test_list(request):

    tests = LabTestMaster.objects.all().order_by('name')
    return render(request, 'lab/test_list.html', {
        'active_sidebar': 'lab',
        'tests': tests,
    })



# NOTE: test_add / test_edit / test_toggle manage the test-rate master
# data (LabTestMaster). The RBAC migration (accounts/0001_create_hospital_
# groups.py) does not currently grant add_labtestmaster or
# change_labtestmaster to ANY group — only LabTech gets view_labtestmaster.
# Adding @permission_required here today would lock every non-superuser
# out of managing the test catalog, which is a bigger behavioral change
# than "enforce the RBAC that already exists." Left as login_required
# only, pending a decision on which group (LabTech? Admin only?) should
# own catalog/rate changes — flagged in TODO.md.
@require_module('lab', level='full')
def test_add(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        rate = request.POST.get('rate', '0').strip()
        if name:
            if LabTestMaster.objects.filter(name__iexact=name).exists():
                messages.error(request, f'Test "{name}" already exists.')
            else:
                LabTestMaster.objects.create(name=name, rate=rate or 0)
                messages.success(request, f'Test "{name}" added successfully.')
                return redirect('lab:test_list')
        else:
            messages.error(request, 'Test name is required.')
    return render(request, 'lab/test_form.html', {
        'active_sidebar': 'lab',
        'action': 'Add',
        'obj': None,
    })


@require_module('lab', level='full')
def test_edit(request, pk):
    test = get_object_or_404(LabTestMaster, pk=pk)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        rate = request.POST.get('rate', '0').strip()
        if name:
            test.name = name
            test.rate = rate or 0
            test.save()
            messages.success(request, f'Test "{name}" updated.')
            return redirect('lab:test_list')
        else:
            messages.error(request, 'Test name is required.')
    return render(request, 'lab/test_form.html', {
        'active_sidebar': 'lab',
        'action': 'Edit',
        'obj': test,
    })


@require_module('lab', level='full')
def test_toggle(request, pk):
    if request.method != 'POST':
        from django.http import HttpResponseNotAllowed
        return HttpResponseNotAllowed(['POST'])
    test = get_object_or_404(LabTestMaster, pk=pk)
    test.is_active = not test.is_active
    test.save()
    status = 'activated' if test.is_active else 'deactivated'
    messages.success(request, f'Test "{test.name}" {status}.')
    return redirect('lab:test_list')


@require_module('lab', level='view')
def patient_lookup(request):
    """AJAX: lookup patient details by OPD No or IPD No.

    Query params:
      - opd_no=<OPD123>
      - ipd_no=<IPD100>

    Response JSON fields:
      patient_name, mobile, guardian, age_years, address, uhid
    """
    opd_no = (request.GET.get('opd_no') or '').strip().upper()
    ipd_no = (request.GET.get('ipd_no') or '').strip().upper()

    if not opd_no and not ipd_no:
        return JsonResponse({'ok': False, 'error': 'opd_no or ipd_no is required'})

    # Normalize inputs
    if opd_no and not opd_no.startswith('OPD'):
        opd_no = f'OPD{opd_no}'
    if ipd_no and not ipd_no.startswith('IPD'):
        ipd_no = f'IPD{ipd_no}'

    try:
        from opd.models import OPDVisit
        from ipd.models import IPDAdmission
    except Exception:
        return JsonResponse({'ok': False, 'error': 'Models import failed'})

    patient = None
    guardian = ''

    if opd_no:
        visit = OPDVisit.objects.select_related('patient').filter(opd_no=opd_no).first()
        if not visit:
            return JsonResponse({'ok': False, 'error': 'OPD No not found'})
        patient = visit.patient
        guardian = visit.referral or ''

    if ipd_no:
        # If both provided, IPD takes precedence (keeps logic simple)
        adm = IPDAdmission.objects.select_related('patient').filter(ipd_no=ipd_no).first()
        if not adm:
            return JsonResponse({'ok': False, 'error': 'IPD No not found'})
        patient = adm.patient
        guardian = adm.guardian or ''

    if not patient:
        return JsonResponse({'ok': False, 'error': 'Patient not found'})

    return JsonResponse({
        'ok': True,
        'patient_name': patient.name or '',
        'mobile': patient.mobile or '',
        'age_years': getattr(patient, 'age_years', '') or '',
        'address': patient.address or '',
        'uhid': patient.uhid or '',
        'guardian': guardian or '',
    })



@require_module('lab', level='view')
def view_report_print(request, pk):
    """Print-friendly report — reuses view_report logic."""
    return view_report(request, pk)


@require_module('lab', level='full')
def investigation_edit(request, pk):
    """Edit lab investigation details (patient name, discount, payment mode, tests)."""
    inv = get_object_or_404(LabInvestigation.objects.prefetch_related('items__test'), pk=pk)
    
    if request.method == 'POST':
        with transaction.atomic():
            old_total = inv.total  # capture before any changes

            # Update investigation header
            inv.patient_name = (request.POST.get('patient_name') or '').strip()
            inv.mobile = request.POST.get('mobile', '')
            inv.address = request.POST.get('address', '')
            inv.consultant = request.POST.get('consultant', '-- Self --')
            inv.referred_by = request.POST.get('referred', 'SELF')
            inv.remarks = request.POST.get('remarks', '')
            inv.discount = Decimal(request.POST.get('discount') or 0)
            inv.payment_mode = request.POST.get('payment_mode', 'Cash')
            inv.test_date = request.POST.get('date') or inv.test_date
            
            # Update tests if changed
            posted_test_ids = request.POST.getlist('tests')
            if posted_test_ids:
                # Clear existing items and rebuild
                inv.items.all().delete()
                
                qty_by_test_id = {}
                for test_id in posted_test_ids:
                    try:
                        qty = int(request.POST.get(f'qty_{test_id}', 1))
                    except (TypeError, ValueError):
                        qty = 1
                    
                    if str(test_id) in qty_by_test_id:
                        qty_by_test_id[str(test_id)] += qty
                    else:
                        qty_by_test_id[str(test_id)] = qty
                
                total = Decimal(0)
                for test_id, qty in qty_by_test_id.items():
                    test = LabTestMaster.objects.filter(pk=test_id).first()
                    if not test:
                        continue
                    
                    item = LabInvestigationItem.objects.create(
                        investigation=inv,
                        test=test,
                        rate=test.rate,
                        quantity=qty,
                    )
                    total += item.amount
                
                inv.total = total - inv.discount
            
            inv.save()

            # BUG-10 FIX: keep IncomeEntry and LedgerEntry in sync with the
            # edited bill total.  Replace the old IncomeEntry row and, if the
            # total changed, replace the LedgerEntry charge+payment pair so
            # the daybook and patient ledger stay accurate.
            new_total = inv.total

            # Replace IncomeEntry
            IncomeEntry.objects.filter(
                description__icontains=f'Lab Bill {inv.bill_no}'
            ).delete()
            if new_total > 0:
                IncomeEntry.objects.create(
                    date=inv.test_date,
                    category='Investigation',
                    patient_name=inv.patient_name,
                    description=f'Lab Bill {inv.bill_no} [edited]',
                    payment_mode=inv.payment_mode,
                    amount=new_total,
                )

            # Replace LedgerEntry rows only when the bill is patient-linked
            # and the total has actually changed (avoids spurious writes).
            if inv.patient and old_total != new_total:
                LedgerEntry.objects.filter(
                    source_app='lab',
                    source_id=inv.bill_no,
                ).delete()
                if new_total > 0:
                    LedgerEntry.record_charge(
                        uhid=inv.patient.uhid,
                        tx_type=LedgerEntry.TxType.LAB_BILL,
                        amount=new_total,
                        payer_type=LedgerEntry.PayerType.PATIENT,
                        description=f'Lab bill {inv.bill_no} [edited]',
                        source_app='lab',
                        source_id=inv.bill_no,
                        patient=inv.patient,
                    )
                    LedgerEntry.record_payment(
                        uhid=inv.patient.uhid,
                        amount=new_total,
                        payer_type=LedgerEntry.PayerType.PATIENT,
                        payment_mode=inv.payment_mode,
                        description=f'Lab bill {inv.bill_no} payment [edited]',
                        source_app='lab',
                        source_id=inv.bill_no,
                        patient=inv.patient,
                    )
        
        messages.success(request, f'Lab bill {inv.bill_no} updated.')
        return redirect('lab:view_all')
    
    # Render edit form
    return render(request, 'lab/investigation_edit.html', {
        'active_sidebar': 'lab',
        'inv': inv,
        'tests': LabTestMaster.objects.filter(is_active=True),
        'today': timezone.localdate().isoformat(),
    })


@require_module('lab', level='full')
@require_POST
def investigation_delete(request, pk):
    """Delete a lab investigation and reverse ledger entries."""
    inv = get_object_or_404(LabInvestigation, pk=pk)
    
    with transaction.atomic():
        # Reverse income entry
        IncomeEntry.objects.filter(
            description__icontains=f'Lab Bill {inv.bill_no}'
        ).delete()
        
        # Reverse ledger entries if linked to patient
        if inv.patient:
            LedgerEntry.objects.filter(
                source_app='lab',
                source_id=inv.bill_no
            ).delete()
        
        inv.delete()
    
    messages.success(request, f'Lab bill {inv.bill_no} deleted.')
    return redirect('lab:view_all')


@require_module('lab', level='full')
def investigation_results(request, pk):
    """Enter or edit test results for a lab investigation."""
    inv = get_object_or_404(LabInvestigation.objects.prefetch_related('items__test', 'items__results'), pk=pk)
    
    if request.method == 'POST':
        with transaction.atomic():
            for item in inv.items.all():
                result_value = request.POST.get(f'result_{item.id}', '').strip()
                unit = request.POST.get(f'unit_{item.id}', '').strip()
                reference_range = request.POST.get(f'ref_{item.id}', '').strip()
                
                # Update or create result
                result_obj, created = LabTestResult.objects.update_or_create(
                    investigation_item=item,
                    defaults={
                        'result_value': result_value,
                        'unit': unit,
                        'reference_range': reference_range,
                    }
                )
        
        messages.success(request, f'Test results saved for {inv.bill_no}.')
        return redirect('lab:view_report', pk=inv.pk)
    
    # Prepare test items with existing results
    test_items = []
    for item in inv.items.all():
        result_obj = item.results.first()
        test_items.append({
            'item': item,
            'test_name': item.test.name,
            'result_value': result_obj.result_value if result_obj else '',
            'unit': result_obj.unit if result_obj else '',
            'reference_range': result_obj.reference_range if result_obj else '',
        })
    
    return render(request, 'lab/investigation_results.html', {
        'active_sidebar': 'lab',
        'inv': inv,
        'test_items': test_items,
    })
