from decimal import Decimal, InvalidOperation

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from uhid.models import Patient

from income.models import LedgerEntry, IncomeEntry

from .models import (
    LabTestMaster,
    LabInvestigation,
    LabInvestigationItem,
)
from core.rbac import require_module


from django.http import JsonResponse




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
            })

        if not patient_name:
            messages.error(request, 'Patient Name is required to submit Lab Investigation.')
            return render(request, 'lab/investigation.html', {
                'active_sidebar': 'lab',
                'tests': LabTestMaster.objects.filter(is_active=True),
                'today': timezone.localdate().isoformat(),
            })

        with transaction.atomic():
            inv = LabInvestigation.objects.create(
                patient=patient,
                patient_name=patient_name,
                mobile=request.POST.get('mobile', ''),
                address=request.POST.get('address', ''),
                consultant=request.POST.get('consultant', '-- Self --'),
                referred_by=request.POST.get('referred', 'SELF'),
                remarks=request.POST.get('remarks', ''),
                discount=Decimal(request.POST.get('discount') or 0),
                payment_mode=request.POST.get('payment_mode', 'Cash'),
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
            
                # duplicate test ko ignore karo
                if str(test_id) not in qty_by_test_id:
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
                    patient=patient,
                )

        messages.success(request, f'Lab bill {inv.bill_no} submitted.')
        return redirect('lab:view_all')

    return render(request, 'lab/investigation.html', {
        'active_sidebar': 'lab',
        'tests': LabTestMaster.objects.filter(is_active=True),
        'today': timezone.localdate().isoformat(),
    })


@require_module('lab', level='view')
def view_all(request):
    # /lab/view-all/ should show the same UI as “Lab Patient List”.
    return patient_list(request)





@require_module('lab', level='view')
def view_report(request, pk):
    inv = get_object_or_404(LabInvestigation.objects.prefetch_related('items__test'), pk=pk)
    report = {
        'bill_no': inv.bill_no,
        'patient': inv.patient_name,
        'date': str(inv.test_date),
        'test_results': [
            {
                'name': i.test.name,
                'result': 'Normal',
                'unit': '-',
                'ref': 'Within range',
            }
            for i in inv.items.all()
        ],
    }
    return render(request, 'lab/view_report.html', {'active_sidebar': 'lab', 'report': report})


@require_module('lab', level='view')
def view_report_print(request, pk):
    # Print-friendly endpoint (same content/template).
    # A dedicated endpoint keeps URLs stable and matches UI “ViewPrint”.
    return view_report(request, pk)


@require_module('lab', level='view')
def patient_list(request):

    q = (request.GET.get('q') or '').strip()

    qs = LabInvestigation.objects.select_related('patient').prefetch_related('items__test').order_by('-created_at')
    if q:
        qs = qs.filter(
            Q(bill_no__icontains=q) |
            Q(patient_name__icontains=q) |
            Q(patient__uhid__icontains=q)
        )

    # Build rows for template
    rows = []
    for inv in qs[:100]:
        patient = getattr(inv, 'patient', None)
        rows.append({

            'name': inv.patient_name,
            'date': str(inv.test_date),
            'time': inv.created_at.strftime('%H:%M') if inv.created_at else '',
            'tests': ', '.join(i.test.name for i in inv.items.all()),
            'bill_no': inv.bill_no,
            'age': getattr(patient, 'age_display', '') if patient else '',
            'consultant': inv.consultant,
            'referred_by': inv.referred_by,

            # LabInvestigation.total is stored as (sum(item.amount) - discount)

            'amount': inv.total if inv.total is not None else '--',

            # Due balance for LAB (PATIENT liability).
            # This column should show patient due (ledger debit - credit for PATIENT).
            'due': (
                (LedgerEntry.patient_due(patient.uhid) if (patient and getattr(patient, 'uhid', None)) else None)
                or '--'
            ),




            'ayushman_card_no': getattr(inv, 'ayushman_card_no', None) or '--',



            'id_proof': getattr(inv, 'id_proof', None) or '--',
        })


    return render(request, 'lab/patient_list.html', {
        'active_sidebar': 'lab',
        'reports': rows,
        'q': q,
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

