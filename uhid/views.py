from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Sum, Q
from django.http import JsonResponse
from .models import Patient
from core.rbac import require_module


INDIAN_STATES = [
    'Andhra Pradesh', 'Arunachal Pradesh', 'Assam', 'Bihar', 'Chhattisgarh',
    'Goa', 'Gujarat', 'Haryana', 'Himachal Pradesh', 'Jharkhand', 'Karnataka',
    'Kerala', 'Madhya Pradesh', 'Maharashtra', 'Manipur', 'Meghalaya', 'Mizoram',
    'Nagaland', 'Odisha', 'Punjab', 'Rajasthan', 'Sikkim', 'Tamil Nadu',
    'Telangana', 'Tripura', 'Uttar Pradesh', 'Uttarakhand', 'West Bengal',
    'Delhi', 'Jammu and Kashmir', 'Ladakh', 'Chandigarh', 'Lakshadweep', 'Puducherry',
]


@require_module('uhid', level='view')
def update(request):
    """Patient list — search + paginated table. No form on this page."""
    search_uhid = (request.GET.get('uhid') or '').strip()
    search_q    = (request.GET.get('q') or '').strip()

    if search_q:
        patients_qs = Patient.objects.filter(
            Q(uhid__icontains=search_q) |
            Q(name__icontains=search_q) |
            Q(mobile__icontains=search_q)
        ).order_by('-created_at')
    elif search_uhid:
        patients_qs = Patient.objects.filter(uhid=search_uhid).order_by('-created_at')
    else:
        patients_qs = Patient.objects.all().order_by('-created_at')

    page = Paginator(patients_qs, 20).get_page(request.GET.get('page', 1))

    return render(request, 'uhid/update.html', {
        'active_sidebar': 'uhid',
        'patients': page,
        'search_uhid': search_uhid,
        'search_q': search_q,
    })


def _save_patient(request, patient=None):
    """Shared save logic used by both register (new) and edit (existing) views."""
    if patient is not None:
        # Editing an existing patient — use the object passed in directly.
        p = patient
    else:
        uhid = (request.POST.get('uhid') or '').strip()
        if uhid:
            # Updating by UHID (fallback path)
            p, _ = Patient.objects.get_or_create(
                uhid=uhid,
                defaults={
                    'name':   (request.POST.get('patient_name') or '').strip(),
                    'mobile': (request.POST.get('mobile') or '').strip(),
                },
            )
        else:
            # Brand-new patient — UHID auto-assigned in Patient.save()
            p = Patient(
                name=(request.POST.get('patient_name') or '').strip(),
                mobile=(request.POST.get('mobile') or '').strip(),
            )

    # Apply all form fields to the patient object
    p.title             = request.POST.get('title', getattr(p, 'title', 'Mr'))
    p.name              = (request.POST.get('patient_name') or p.name).strip()
    p.gender            = request.POST.get('gender', getattr(p, 'gender', 'Male'))
    p.marital_status    = request.POST.get('marital', getattr(p, 'marital_status', 'Single'))
    p.guardian          = (request.POST.get('guardian') or '').strip()
    p.guardian_relation = request.POST.get('guardian_relation', getattr(p, 'guardian_relation', 'S/o'))
    p.mobile            = (request.POST.get('mobile') or getattr(p, 'mobile', '')).strip()
    p.blood_group       = request.POST.get('blood_group', getattr(p, 'blood_group', 'NA'))
    p.state             = (request.POST.get('state') or '').strip()
    p.city              = (request.POST.get('city') or '').strip()
    p.address           = (request.POST.get('address') or '').strip()

    # DOB: update if a new value was submitted
    dob_raw = (request.POST.get('dob') or '').strip()
    if dob_raw:
        try:
            from datetime import date as _date
            p.dob = _date.fromisoformat(dob_raw)   # converts "YYYY-MM-DD" string → date object
        except (ValueError, TypeError):
            pass  # ignore invalid date strings

    if p.dob:
        # Auto-calculate age from DOB (p.dob is guaranteed a date object here)
        from datetime import date
        from dateutil.relativedelta import relativedelta
        try:
            delta = relativedelta(date.today(), p.dob)
            p.age_years  = max(0, delta.years)
            p.age_months = max(0, delta.months)
            p.age_days   = max(0, delta.days)
        except Exception:
            pass
    else:
        # Manual age entry when DOB is unknown
        try:
            p.age_years = max(0, int(request.POST.get('age_years') or 0))
        except (ValueError, TypeError):
            pass
        try:
            p.age_months = max(0, min(11, int(request.POST.get('age_months') or 0)))
        except (ValueError, TypeError):
            pass

    p.save()
    return p


@require_module('uhid', level='view')
def register(request):
    """New patient registration form at /uhid/register/"""
    if request.method == 'POST':
        if getattr(request, 'is_view_only', False):
            raise PermissionDenied("Your role has view-only access to UHID records.")
        if not (request.POST.get('patient_name') or '').strip():
            messages.error(request, 'Patient name is required.')
            return render(request, 'uhid/register.html', {
                'active_sidebar': 'uhid',
                'patient': {},
                'indian_states': INDIAN_STATES,
            })
        p = _save_patient(request)
        messages.success(request, f'Patient registered — UHID: {p.uhid}')
        return redirect('uhid:update')

    return render(request, 'uhid/register.html', {
        'active_sidebar': 'uhid',
        'patient': {},
        'indian_states': INDIAN_STATES,
    })


@require_module('uhid', level='view')
def edit(request, uhid):
    """Edit an existing patient record at /uhid/edit/<uhid>/"""
    patient = get_object_or_404(Patient, uhid=uhid)

    if request.method == 'POST':
        if getattr(request, 'is_view_only', False):
            raise PermissionDenied("Your role has view-only access to UHID records.")
        if not (request.POST.get('patient_name') or '').strip():
            messages.error(request, 'Patient name is required.')
            return render(request, 'uhid/register.html', {
                'active_sidebar': 'uhid',
                'patient': patient,
                'indian_states': INDIAN_STATES,
            })
        p = _save_patient(request, patient=patient)
        messages.success(request, f'Patient updated — UHID: {p.uhid}')
        return redirect('uhid:patient_profile', uhid=p.uhid)

    return render(request, 'uhid/register.html', {
        'active_sidebar': 'uhid',
        'patient': patient,
        'indian_states': INDIAN_STATES,
    })


@require_module('uhid', level='view')
def patient_profile(request, uhid):
    """Read-only patient profile — full history across all modules."""
    patient = get_object_or_404(Patient, uhid=uhid)

    opd_visits    = patient.opd_visits.order_by('-date', '-time')[:20]
    ipd_admissions = patient.ipd_admissions.order_by('-date')[:10]
    lab_bills     = patient.lab_bills.prefetch_related('items__test').order_by('-test_date')[:20]

    try:
        usg_bills = patient.ultrasound_bills.prefetch_related('items__test', 'documents').order_by('-test_date')[:20]
    except Exception:
        usg_bills = []

    # Aggregate all ultrasound documents across all bills for display on profile
    usg_documents = []
    try:
        from ultrasound.models import UltrasoundDocument
        docs_qs = (
            UltrasoundDocument.objects
            .filter(investigation__patient=patient)
            .select_related('investigation')
            .order_by('-investigation__test_date', '-uploaded_at')
        )
        for doc in docs_qs:
            usg_documents.append({
                'filename': doc.file.name.split('/')[-1],
                'url': doc.file.url,
                'bill_no': doc.investigation.bill_no,
                'test_date': doc.investigation.test_date,
                'investigation_id': doc.investigation.id,
            })
    except Exception:
        usg_documents = []

    from income.models import LedgerEntry
    agg = LedgerEntry.objects.filter(patient=patient).aggregate(
        total_charged=Sum('debit_amount'),
        total_paid=Sum('credit_amount'),
    )
    total_charged = agg['total_charged'] or 0
    total_paid    = agg['total_paid']    or 0
    outstanding   = total_charged - total_paid

    return render(request, 'uhid/patient_profile.html', {
        'active_sidebar': 'uhid',
        'patient': patient,
        'opd_visits': opd_visits,
        'ipd_admissions': ipd_admissions,
        'lab_bills': lab_bills,
        'usg_bills': usg_bills,
        'usg_documents': usg_documents,
        'total_charged': total_charged,
        'total_paid': total_paid,
        'outstanding': outstanding,
    })


@require_module('uhid', level='view')
def patient_search_api(request):
    """JSON API for UHID/patient search — used by modal dialogs."""
    q = (request.GET.get('q') or '').strip()
    if not q or len(q) < 2:
        return JsonResponse({'results': []})
    
    patients = Patient.objects.filter(
        Q(uhid__icontains=q) |
        Q(name__icontains=q) |
        Q(mobile__icontains=q)
    ).values('uhid', 'name', 'mobile', 'age_years', 'gender')[:10]
    
    return JsonResponse({'results': list(patients)})
