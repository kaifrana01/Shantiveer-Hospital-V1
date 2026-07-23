from django.shortcuts import render, redirect
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
        )
        messages.success(request, 'Doctor added.')
        return redirect('masterdata:doctor_list')
    return render(request, 'masterdata/doctors.html', {'active_sidebar': 'master'})


@require_module('masterdata', level='full')
def doctor_list(request):
    return render(request, 'masterdata/doctor_list.html', {'active_sidebar': 'master', 'doctors': Doctor.objects.filter(is_active=True)})
