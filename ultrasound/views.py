"""
Ultrasound module views — fully standalone dashboard, billing, patient list,
income/expense charts and reports. Completely separate from other HMS modules.
"""
import json
from decimal import Decimal, InvalidOperation
from datetime import date, timedelta
from collections import defaultdict

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Sum, Count
from django.utils import timezone
from django.http import JsonResponse

from uhid.models import Patient
from income.models import LedgerEntry, IncomeEntry

from .models import (
    UltrasoundTestMaster,
    UltrasoundInvestigation,
    UltrasoundInvestigationItem,
    UltrasoundDocument,
    UltrasoundExpense,
)
from core.rbac import require_module


# ─── Dashboard ────────────────────────────────────────────────────────────────

@require_module('ultrasound', level='view')
def dashboard(request):
    today = timezone.localdate()
    month_start = today.replace(day=1)

    # KPIs
    today_bills = UltrasoundInvestigation.objects.filter(test_date=today)
    month_bills = UltrasoundInvestigation.objects.filter(test_date__gte=month_start)
    today_income = today_bills.aggregate(s=Sum('total'))['s'] or Decimal('0')
    month_income = month_bills.aggregate(s=Sum('total'))['s'] or Decimal('0')
    today_count = today_bills.count()
    month_count = month_bills.count()

    today_expenses = UltrasoundExpense.objects.filter(date=today)
    month_expenses = UltrasoundExpense.objects.filter(date__gte=month_start)
    today_exp_amt = today_expenses.aggregate(s=Sum('amount'))['s'] or Decimal('0')
    month_exp_amt = month_expenses.aggregate(s=Sum('amount'))['s'] or Decimal('0')

    # Net profit
    today_net = today_income - today_exp_amt
    month_net = month_income - month_exp_amt

    # Last 30 days chart data (income + expenses per day)
    # NOTE: Avoid TruncDate/TruncMonth on SQLite because it can fail when
    # historical/dirty rows contain invalid date strings.
    thirty_ago = today - timedelta(days=29)

    inc_rows = UltrasoundInvestigation.objects.filter(
        test_date__gte=thirty_ago
    ).values_list('test_date', 'total')
    exp_rows = UltrasoundExpense.objects.filter(
        date__gte=thirty_ago
    ).values_list('date', 'amount')

    inc_map = {}
    for d, amt in inc_rows:
        if d is None:
            continue
        inc_map[d] = float(inc_map.get(d, 0) + (amt or 0))

    exp_map = {}
    for d, amt in exp_rows:
        if d is None:
            continue
        exp_map[d] = float(exp_map.get(d, 0) + (amt or 0))

    chart_labels = []
    chart_income = []
    chart_expenses = []
    for i in range(30):
        d = thirty_ago + timedelta(days=i)
        chart_labels.append(d.strftime('%d %b'))
        chart_income.append(inc_map.get(d, 0))
        chart_expenses.append(exp_map.get(d, 0))

    # Monthly trend (last ~6 months)
    six_ago = today.replace(day=1) - timedelta(days=150)

    monthly_inc_rows = UltrasoundInvestigation.objects.filter(
        test_date__gte=six_ago
    ).values_list('test_date', 'total')
    monthly_exp_rows = UltrasoundExpense.objects.filter(
        date__gte=six_ago
    ).values_list('date', 'amount')

    monthly_inc_map = {}
    for d, amt in monthly_inc_rows:
        if d is None:
            continue
        key = d.strftime('%b %Y')
        monthly_inc_map[key] = float(monthly_inc_map.get(key, 0) + (amt or 0))

    monthly_exp_map = {}
    for d, amt in monthly_exp_rows:
        if d is None:
            continue
        key = d.strftime('%b %Y')
        monthly_exp_map[key] = float(monthly_exp_map.get(key, 0) + (amt or 0))

    all_months = sorted(set(monthly_inc_map.keys()) | set(monthly_exp_map.keys()))

    monthly_chart_labels = all_months
    monthly_chart_income = [monthly_inc_map.get(m, 0) for m in all_months]
    monthly_chart_expenses = [monthly_exp_map.get(m, 0) for m in all_months]


    # Test popularity
    test_stats = (
        UltrasoundInvestigationItem.objects
        .values('test__name')
        .annotate(count=Count('id'), revenue=Sum('amount'))
        .order_by('-count')[:8]
    )

    # Recent bills
    recent_bills = UltrasoundInvestigation.objects.prefetch_related('items__test').order_by('-created_at')[:8]

    # Payment mode distribution
    payment_dist = (
        UltrasoundInvestigation.objects
        .filter(test_date__gte=month_start)
        .values('payment_mode')
        .annotate(total=Sum('total'), count=Count('id'))
    )

    # Expense breakdown by category
    exp_by_cat = (
        UltrasoundExpense.objects
        .filter(date__gte=month_start)
        .values('category')
        .annotate(total=Sum('amount'))
        .order_by('-total')
    )

    context = {
        'active_sidebar': 'ultrasound_dashboard',
        # KPIs
        'today_income': today_income,
        'today_expenses': today_exp_amt,
        'today_net': today_net,
        'today_count': today_count,
        'month_income': month_income,
        'month_expenses': month_exp_amt,
        'month_net': month_net,
        'month_count': month_count,
        # Charts (JSON for JS)
        'chart_labels': json.dumps(chart_labels),
        'chart_income': json.dumps(chart_income),
        'chart_expenses': json.dumps(chart_expenses),
        'monthly_chart_labels': json.dumps(monthly_chart_labels),
        'monthly_chart_income': json.dumps(monthly_chart_income),
        'monthly_chart_expenses': json.dumps(monthly_chart_expenses),
        # Tables
        'test_stats': list(test_stats),
        'recent_bills': recent_bills,
        'payment_dist': list(payment_dist),
        'exp_by_cat': list(exp_by_cat),
        'today': today,
    }
    return render(request, 'ultrasound/dashboard.html', context)


# ─── Billing ──────────────────────────────────────────────────────────────────

@require_module('ultrasound', level='full')
def ultrasound_investigation(request):
    if request.method == 'POST':
        patient = None
        uhid = request.POST.get('uhid')
        if uhid:
            patient = Patient.objects.filter(uhid=uhid).first()

        patient_name = (request.POST.get('patient_name') or '').strip()
        selected_tests = request.POST.getlist('tests')

        ctx = {
            'active_sidebar': 'ultrasound',
            'tests': UltrasoundTestMaster.objects.filter(is_active=True),
            'today': timezone.localdate().isoformat(),
        }

        if not selected_tests:
            messages.error(request, 'Please select at least one ultrasound test.')
            return render(request, 'ultrasound/ultrasound_form.html', ctx)

        if not patient_name:
            messages.error(request, 'Patient Name is required.')
            return render(request, 'ultrasound/ultrasound_form.html', ctx)

        with transaction.atomic():
            inv = UltrasoundInvestigation.objects.create(
                patient=patient,
                patient_name=patient_name,
                age=request.POST.get('age', ''),
                gender=request.POST.get('gender', ''),
                mobile=request.POST.get('mobile', ''),
                address=request.POST.get('address', ''),
                consultant=request.POST.get('consultant', '-- Self --'),
                referred_by=request.POST.get('referred', 'SELF'),
                remarks=request.POST.get('remarks', ''),
                discount=Decimal(request.POST.get('discount') or 0),
                payment_mode=request.POST.get('payment_mode', 'Cash'),
                test_date=request.POST.get('date') or timezone.localdate(),
            )

            total = Decimal(0)
            for test_id in selected_tests:
                test = UltrasoundTestMaster.objects.filter(pk=test_id).first()
                if test:
                    raw_rate = request.POST.get(f'rate_{test_id}')
                    try:
                        custom_rate = Decimal(raw_rate) if raw_rate not in (None, '') else test.rate
                        if custom_rate < 0:
                            custom_rate = test.rate
                    except (InvalidOperation, ValueError):
                        custom_rate = test.rate

                    item = UltrasoundInvestigationItem.objects.create(
                        investigation=inv, test=test, rate=custom_rate, quantity=1,
                    )
                    total += item.amount

            inv.total = total - inv.discount
            inv.save()

            # Record in central income ledger
            IncomeEntry.objects.create(
                date=inv.test_date,
                category='Investigation',
                patient_name=inv.patient_name,
                description=f'Ultrasound Bill {inv.bill_no}',
                payment_mode=inv.payment_mode,
                amount=inv.total,
            )

            if patient and inv.total > 0:
                LedgerEntry.record_charge(
                    uhid=patient.uhid,
                    tx_type=LedgerEntry.TxType.LAB_BILL,
                    amount=inv.total,
                    payer_type=LedgerEntry.PayerType.PATIENT,
                    description=f'Ultrasound bill {inv.bill_no}',
                    source_app='ultrasound',
                    source_id=inv.bill_no,
                    patient=patient,
                )
                LedgerEntry.record_payment(
                    uhid=patient.uhid,
                    amount=inv.total,
                    payer_type=LedgerEntry.PayerType.PATIENT,
                    payment_mode=inv.payment_mode,
                    description=f'Ultrasound bill {inv.bill_no} payment collected',
                    patient=patient,
                )

            for f in request.FILES.getlist('documents'):
                UltrasoundDocument.objects.create(investigation=inv, file=f)

        messages.success(request, f'Ultrasound bill {inv.bill_no} created successfully.')
        return redirect('ultrasound:patient_list')

    return render(request, 'ultrasound/ultrasound_form.html', {
        'active_sidebar': 'ultrasound',
        'tests': UltrasoundTestMaster.objects.filter(is_active=True),
        'today': timezone.localdate().isoformat(),
    })


# ─── Patient / Bill List ───────────────────────────────────────────────────────

@require_module('ultrasound', level='view')
def patient_list(request):
    q = request.GET.get('q', '').strip()
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    payment_filter = request.GET.get('payment', '')

    qs = UltrasoundInvestigation.objects.prefetch_related('items__test')

    if q:
        qs = qs.filter(
            Q(bill_no__icontains=q) |
            Q(patient_name__icontains=q) |
            Q(mobile__icontains=q)
        )
    if date_from:
        qs = qs.filter(test_date__gte=date_from)
    if date_to:
        qs = qs.filter(test_date__lte=date_to)
    if payment_filter:
        qs = qs.filter(payment_mode=payment_filter)

    total_amount = qs.aggregate(s=Sum('total'))['s'] or Decimal('0')

    return render(request, 'ultrasound/patient_list.html', {
        'active_sidebar': 'ultrasound',
        'bills': qs[:100],
        'q': q,
        'date_from': date_from,
        'date_to': date_to,
        'payment_filter': payment_filter,
        'total_amount': total_amount,
        'total_count': qs.count(),
    })


# ─── Bill / Report detail ──────────────────────────────────────────────────────

@require_module('ultrasound', level='view')
def ultrasound_view_report(request, pk):
    inv = get_object_or_404(
        UltrasoundInvestigation.objects.prefetch_related('items__test', 'documents'), pk=pk,
    )
    report = {
        'bill_no': inv.bill_no,
        'patient': inv.patient_name,
        'age': inv.age,
        'gender': inv.gender,
        'mobile': inv.mobile,
        'address': inv.address,
        'consultant': inv.consultant,
        'referred_by': inv.referred_by,
        'date': str(inv.test_date),
        'payment_mode': inv.payment_mode,
        'remarks': inv.remarks,
        'items': [
            {'name': it.test.name, 'rate': it.rate, 'qty': it.quantity, 'amount': it.amount}
            for it in inv.items.all()
        ],
        'subtotal': inv.total + inv.discount,
        'discount': inv.discount,
        'payable': inv.total,
        'documents': [
            {'name': d.file.name.split('/')[-1], 'url': d.file.url}
            for d in inv.documents.all()
        ],
    }
    return render(request, 'ultrasound/bill_detail.html', {
        'active_sidebar': 'ultrasound',
        'report': report,
        'inv': inv,
    })


# ─── Test Master ──────────────────────────────────────────────────────────────

@require_module('ultrasound', level='view')
def test_list(request):
    tests = UltrasoundTestMaster.objects.all().order_by('name')
    return render(request, 'ultrasound/test_list.html', {
        'active_sidebar': 'ultrasound',
        'tests': tests,
    })


@require_module('ultrasound', level='full')
def test_add(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        rate = request.POST.get('rate', '0').strip()
        if name:
            if UltrasoundTestMaster.objects.filter(name__iexact=name).exists():
                messages.error(request, f'Test "{name}" already exists.')
            else:
                UltrasoundTestMaster.objects.create(name=name, rate=rate or 0)
                messages.success(request, f'Test "{name}" added.')
                return redirect('ultrasound:test_list')
        else:
            messages.error(request, 'Test name is required.')
    return render(request, 'ultrasound/test_form.html', {
        'active_sidebar': 'ultrasound', 'action': 'Add', 'obj': None,
    })


@require_module('ultrasound', level='full')
def test_edit(request, pk):
    test = get_object_or_404(UltrasoundTestMaster, pk=pk)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        rate = request.POST.get('rate', '0').strip()
        if name:
            test.name = name
            test.rate = rate or 0
            test.save()
            messages.success(request, f'Test "{name}" updated.')
            return redirect('ultrasound:test_list')
        else:
            messages.error(request, 'Test name is required.')
    return render(request, 'ultrasound/test_form.html', {
        'active_sidebar': 'ultrasound', 'action': 'Edit', 'obj': test,
    })


@require_module('ultrasound', level='full')
def test_toggle(request, pk):
    test = get_object_or_404(UltrasoundTestMaster, pk=pk)
    test.is_active = not test.is_active
    test.save()
    messages.success(request, f'Test "{test.name}" {"activated" if test.is_active else "deactivated"}.')
    return redirect('ultrasound:test_list')


# ─── Expenses ─────────────────────────────────────────────────────────────────

@require_module('ultrasound', level='view')
def expenses(request):
    if request.method == 'POST' and not request.is_view_only:
        date_val = request.POST.get('date') or timezone.localdate()
        cat = request.POST.get('category', 'other')
        desc = request.POST.get('description', '').strip()
        amount = request.POST.get('amount', '0')
        remarks = request.POST.get('remarks', '').strip()

        if not desc:
            messages.error(request, 'Description is required.')
        else:
            try:
                amt = Decimal(amount)
                if amt <= 0:
                    raise ValueError
                UltrasoundExpense.objects.create(
                    date=date_val, category=cat, description=desc,
                    amount=amt, remarks=remarks
                )
                messages.success(request, 'Expense recorded.')
                return redirect('ultrasound:expenses')
            except (InvalidOperation, ValueError):
                messages.error(request, 'Invalid amount.')

    qs = UltrasoundExpense.objects.order_by('-date', '-created_at')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)

    total = qs.aggregate(s=Sum('amount'))['s'] or Decimal('0')

    return render(request, 'ultrasound/expenses.html', {
        'active_sidebar': 'ultrasound',
        'expenses': qs[:100],
        'total': total,
        'date_from': date_from,
        'date_to': date_to,
        'today': timezone.localdate().isoformat(),
        'categories': UltrasoundExpense.CATEGORY_CHOICES,
    })
