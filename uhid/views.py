from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from .models import Patient
from core.rbac import require_module


@require_module('uhid', level='view')
def update(request):
    search_uhid = (request.GET.get('uhid') or '').strip()
    patient = None
    if search_uhid:
        patient = Patient.objects.filter(uhid=search_uhid).first()

    if request.method == 'POST':
        if getattr(request, 'is_view_only', False):
            raise PermissionDenied("Your role has view-only access to UHID records.")

        # POST may carry an existing UHID (hidden field) or we use the GET param
        uhid = (request.POST.get('uhid') or search_uhid or '').strip()

        if uhid:
            # Update existing patient
            p, _ = Patient.objects.get_or_create(
                uhid=uhid,
                defaults={
                    'name': (request.POST.get('patient_name') or '').strip(),
                    'mobile': (request.POST.get('mobile') or '').strip(),
                },
            )
        else:
            # New patient — system auto-assigns UHID on save
            p = Patient(
                name=(request.POST.get('patient_name') or '').strip(),
                mobile=(request.POST.get('mobile') or '').strip(),
            )

        p.title          = request.POST.get('title', p.title)
        p.name           = (request.POST.get('patient_name') or p.name).strip()
        p.gender         = request.POST.get('gender', p.gender)
        p.marital_status = request.POST.get('marital', p.marital_status)
        p.guardian       = (request.POST.get('guardian') or '').strip()
        p.guardian_relation = request.POST.get('guardian_relation', p.guardian_relation)
        p.mobile         = (request.POST.get('mobile') or p.mobile).strip()
        p.blood_group    = request.POST.get('blood_group', p.blood_group)
        p.state          = (request.POST.get('state') or '').strip()
        p.city           = (request.POST.get('city') or '').strip()
        p.address        = (request.POST.get('address') or '').strip()

        if request.POST.get('dob'):
            p.dob = request.POST.get('dob')

        # Auto-calculate age from DOB
        if p.dob:
            from datetime import date
            from dateutil.relativedelta import relativedelta
            today = date.today()
            dob = p.dob
            try:
                delta = relativedelta(today, dob)
                p.age_years  = max(0, delta.years)
                p.age_months = max(0, delta.months)
                p.age_days   = max(0, delta.days)
            except Exception:
                pass

        p.save()
        messages.success(request, f'Patient record saved — UHID: {p.uhid}')
        return redirect(f'{request.path}?uhid={p.uhid}')

    INDIAN_STATES = [
        'Andhra Pradesh', 'Arunachal Pradesh', 'Assam', 'Bihar', 'Chhattisgarh',
        'Goa', 'Gujarat', 'Haryana', 'Himachal Pradesh', 'Jharkhand', 'Karnataka',
        'Kerala', 'Madhya Pradesh', 'Maharashtra', 'Manipur', 'Meghalaya', 'Mizoram',
        'Nagaland', 'Odisha', 'Punjab', 'Rajasthan', 'Sikkim', 'Tamil Nadu',
        'Telangana', 'Tripura', 'Uttar Pradesh', 'Uttarakhand', 'West Bengal',
        'Delhi', 'Jammu and Kashmir', 'Ladakh', 'Chandigarh', 'Lakshadweep', 'Puducherry',
    ]

    # Search by name/mobile in addition to UHID
    search_q = (request.GET.get('q') or '').strip()
    from django.db.models import Q
    if search_q:
        patients_qs = Patient.objects.filter(
            Q(uhid__icontains=search_q) |
            Q(name__icontains=search_q) |
            Q(mobile__icontains=search_q)
        ).order_by('-created_at')
    else:
        patients_qs = Patient.objects.all().order_by('-created_at')

    page = Paginator(patients_qs, 20).get_page(request.GET.get('page', 1))

    return render(request, 'uhid/update.html', {
        'active_sidebar': 'uhid',
        'patients': page,
        'search_uhid': search_uhid,
        'search_q': search_q,
        'patient': patient or {},
        'indian_states': INDIAN_STATES,
    })
