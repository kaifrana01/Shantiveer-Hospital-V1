from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from .models import Doctor, TestInterpretation
from lab.models import LabTestMaster
from core.rbac import require_module


@require_module('masterdata', level='full')
def interpretation(request):
    if request.method == 'POST':
        TestInterpretation.objects.create(
            test_name=request.POST.get('test', request.POST.get('test_name', '')),
            interpretation=request.POST.get('interpretation', ''),
        )
        messages.success(request, 'Interpretation added.')
        return redirect('masterdata:interpretation')
    q = request.GET.get('q', '').strip()
    qs = TestInterpretation.objects.all()
    if q:
        qs = qs.filter(test_name__icontains=q)
    tests = list(LabTestMaster.objects.values_list('name', flat=True)) or ['NT-PRO-BNP', 'CBC', 'KFT']
    return render(request, 'masterdata/interpretation.html', {
        'active_sidebar': 'master', 'tests': tests, 'interpretations': qs,
    })


@require_module('masterdata', level='full')
def doctors(request):
    if request.method == 'POST':
        Doctor.objects.create(
            name=request.POST.get('name', ''),
            department=request.POST.get('department', ''),
            specialization=request.POST.get('specialization', ''),
            phone=request.POST.get('phone', ''),
            email=request.POST.get('email', ''),
            gender=request.POST.get('gender', ''),
            qualification=request.POST.get('qualification', ''),
            registration_number=request.POST.get('registration_number', ''),
            experience_years=request.POST.get('experience_years') or None,
            date_of_joining=request.POST.get('date_of_joining') or None,
            dob=request.POST.get('dob') or None,
            address=request.POST.get('address', ''),
        )
        messages.success(request, 'Doctor added.')
        return redirect('masterdata:doctor_list')
    return render(request, 'masterdata/doctors.html', {'active_sidebar': 'master'})


@require_module('masterdata', level='full')
def doctor_list(request):
    return render(request, 'masterdata/doctor_list.html', {'active_sidebar': 'master', 'doctors': Doctor.objects.filter(is_active=True)})



@require_module('masterdata', level='full')
def doctor_edit(request, pk):
    """Edit doctor details."""
    doctor = get_object_or_404(Doctor, pk=pk)
    if request.method == 'POST':
        doctor.name = request.POST.get('name', doctor.name)
        doctor.department = request.POST.get('department', doctor.department)
        doctor.specialization = request.POST.get('specialization', doctor.specialization)
        doctor.phone = request.POST.get('phone', doctor.phone)
        doctor.email = request.POST.get('email', doctor.email)
        doctor.gender = request.POST.get('gender', doctor.gender)
        doctor.qualification = request.POST.get('qualification', doctor.qualification)
        doctor.registration_number = request.POST.get('registration_number', doctor.registration_number)
        doctor.experience_years = request.POST.get('experience_years') or None
        doctor.date_of_joining = request.POST.get('date_of_joining') or None
        doctor.dob = request.POST.get('dob') or None
        doctor.address = request.POST.get('address', doctor.address)
        doctor.save()
        messages.success(request, f'Doctor "{doctor.name}" updated.')
        return redirect('masterdata:doctor_list')
    
    return render(request, 'masterdata/doctor_edit.html', {
        'active_sidebar': 'master',
        'doctor': doctor,
    })


@require_module('masterdata', level='full')
def doctor_toggle(request, pk):
    """Toggle doctor active status."""
    if request.method != 'POST':
        from django.http import HttpResponseNotAllowed
        return HttpResponseNotAllowed(['POST'])
    doctor = get_object_or_404(Doctor, pk=pk)
    doctor.is_active = not doctor.is_active
    doctor.save()
    status = 'activated' if doctor.is_active else 'deactivated'
    messages.success(request, f'Doctor "{doctor.name}" {status}.')
    return redirect('masterdata:doctor_list')


@require_module('masterdata', level='full')
def interpretation_edit(request, pk):
    """Edit test interpretation."""
    interp = get_object_or_404(TestInterpretation, pk=pk)
    if request.method == 'POST':
        interp.test_name = request.POST.get('test', interp.test_name)
        interp.interpretation = request.POST.get('interpretation', interp.interpretation)
        interp.save()
        messages.success(request, f'Interpretation for "{interp.test_name}" updated.')
        return redirect('masterdata:interpretation')
    
    tests = list(LabTestMaster.objects.values_list('name', flat=True)) or ['NT-PRO-BNP', 'CBC', 'KFT']
    return render(request, 'masterdata/interpretation_edit.html', {
        'active_sidebar': 'master',
        'interp': interp,
        'tests': tests,
    })


@require_module('masterdata', level='full')
def interpretation_delete(request, pk):
    """Delete test interpretation."""
    interp = get_object_or_404(TestInterpretation, pk=pk)
    test_name = interp.test_name
    interp.delete()
    messages.success(request, f'Interpretation for "{test_name}" deleted.')
    return redirect('masterdata:interpretation')
