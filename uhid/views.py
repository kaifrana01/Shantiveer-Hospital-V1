from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from .models import Patient
from core.rbac import require_module


@require_module('uhid', level='view')
def update(request):
    search_uhid = request.GET.get('uhid', '')
    patient = None
    if search_uhid:
        patient = Patient.objects.filter(uhid=search_uhid).first()

    if request.method == 'POST':
        if getattr(request, 'is_view_only', False):
            raise PermissionDenied("Your role has view-only access to UHID records.")
        uhid = request.POST.get('uhid') or search_uhid
        p, _ = Patient.objects.get_or_create(uhid=uhid, defaults={'name': request.POST.get('patient_name', ''), 'mobile': request.POST.get('mobile', '')})
        p.title = request.POST.get('title', p.title)
        p.name = request.POST.get('patient_name', p.name)
        p.gender = request.POST.get('gender', p.gender)
        p.marital_status = request.POST.get('marital', p.marital_status)
        p.mobile = request.POST.get('mobile', p.mobile)
        p.blood_group = request.POST.get('blood_group', p.blood_group)
        p.address = request.POST.get('address', p.address)
        if request.POST.get('dob'):
            p.dob = request.POST.get('dob')

        # Auto-calculate age from DOB
        if p.dob:
            from datetime import date
            today = date.today()
            dob = p.dob
            years = today.year - dob.year
            # If birthday hasn't occurred yet this year, subtract one.
            if (today.month, today.day) < (dob.month, dob.day):
                years -= 1

            # Months + days after the last birthday
            last_birthday_year = dob.year + years
            # Handle Feb 29 birthdays by clamping to Feb 28/Mar 1 depending on today's calendar.
            try:
                last_birthday = date(last_birthday_year, dob.month, dob.day)
            except ValueError:
                # For Feb 29, use Feb 28 as last birthday
                last_birthday = date(last_birthday_year, 2, 28)

            # First day after last birthday
            if last_birthday > today:
                # Edge-case: DOB set to future date
                years = 0
                p.age_years = 0
                p.age_months = 0
                p.age_days = 0
            else:
                from dateutil.relativedelta import relativedelta
                delta = relativedelta(today, last_birthday)
                p.age_years = max(0, years)
                p.age_months = max(0, delta.months)
                p.age_days = max(0, delta.days)

        p.save()

        messages.success(request, 'UHID record saved.')
        return redirect('uhid:update')

    patients = Patient.objects.all()
    page = Paginator(patients, 10).get_page(request.GET.get('page', 1))

    return render(request, 'uhid/update.html', {
        'active_sidebar': 'uhid',
        'patients': page,
        'search_uhid': search_uhid,
        'patient': patient or {},
    })
