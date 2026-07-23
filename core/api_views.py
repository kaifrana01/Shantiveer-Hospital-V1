from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.response import Response
from django.db.models import Q, Count, Sum
from django.core.cache import cache
from uhid.models import Patient
from core import services

import logging
from typing import Optional

logger = logging.getLogger('hms.dashboard')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@throttle_classes([ScopedRateThrottle])
def dashboard_stats(request):
    from opd.models import OPDVisit
    from income.models import IncomeEntry
    from django.db.models.functions import TruncMonth, TruncDay
    from django.utils import timezone
    from datetime import timedelta

    range_filter = request.GET.get('range', 'month')
    if range_filter not in services.VALID_RANGES:
        # Don't let an arbitrary client-supplied string flow into ORM
        # date math or cache keys — fall back to a safe default instead
        # of erroring or silently misbehaving.
        range_filter = 'month'
    today = timezone.localdate()

    # Expenses chart data (basic + advance combined)
    try:
        from expenses.models import Expense
        from core.services import get_dashboard_expenses_timeseries

        labels, values = get_dashboard_expenses_timeseries(expense_type=None, range_filter=range_filter)
    except Exception:
        labels, values = (['0'], [0])


    # Build date filter for patient chart
    if range_filter == 'today':
        date_from = today
        trunc_fn = TruncDay
        fmt = '%H:00'
    elif range_filter == 'week':
        date_from = today - timedelta(days=6)
        trunc_fn = TruncDay
        fmt = '%a'
    elif range_filter == 'year':
        date_from = today.replace(month=1, day=1)
        trunc_fn = TruncMonth
        fmt = '%b'
    else:  # month
        date_from = today - timedelta(days=29)
        trunc_fn = TruncDay
        fmt = '%d %b'

    months = (
        OPDVisit.objects
        .filter(date__gte=date_from)
        .annotate(m=trunc_fn('date'))
        .values('m')
        .annotate(c=Count('id'))
        .order_by('m')[:8]
    )
    labels = [x['m'].strftime(fmt) if x['m'] else '' for x in months] or ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul']
    counts = [x['c'] for x in months] or [40, 55, 45, 70, 60, 80, 75]

    # Patient old/new: old = visited more than once
    total_patients = Patient.objects.count()
    old_patients = (
        Patient.objects.annotate(visit_count=Count('opd_visits'))
        .filter(visit_count__gt=1)
        .count()
    )
    new_patients = total_patients - old_patients

    # Revenue: grouped by range
    income_total_qs = IncomeEntry.objects.all()
    if range_filter == 'today':
        income_total_qs = income_total_qs.filter(date=today)
        rev_rows = (
            income_total_qs
            .annotate(d=TruncDay('date')).values('d')
            .annotate(s=Sum('amount')).order_by('d')
        )
        rev_labels = [today.strftime('%d %b')]
        rev_values = [float(list(rev_rows)[0]['s']) if rev_rows else 0]
    elif range_filter == 'year':
        income_total_qs = income_total_qs.filter(date__gte=today.replace(month=1, day=1))
        from django.db.models.functions import TruncMonth as TM
        rev_rows = (
            income_total_qs
            .annotate(d=TM('date')).values('d')
            .annotate(s=Sum('amount')).order_by('d')
        )
        import calendar
        rev_labels = [calendar.month_abbr[i] for i in range(1, 13)]
        rev_map_yr = {r['d'].month: float(r['s'] or 0) for r in rev_rows}
        rev_values = [rev_map_yr.get(i, 0) for i in range(1, 13)]
    elif range_filter == 'month':
        income_total_qs = income_total_qs.filter(date__gte=today - timedelta(days=29))
        rev_rows = (
            income_total_qs
            .annotate(d=TruncDay('date')).values('d')
            .annotate(s=Sum('amount')).order_by('d')
        )
        rev_labels = [(today - timedelta(days=29 - i)).strftime('%d') for i in range(30)]
        # In Django 6, TruncDay('date') values are already date objects when using values('d').
        rev_map = {r['d']: float(r['s'] or 0) for r in rev_rows}
        rev_values = [rev_map.get(today - timedelta(days=29 - i), 0) for i in range(30)]
    else:  # week
        income_total_qs = income_total_qs.filter(date__gte=today - timedelta(days=6))
        rev_rows = (
            income_total_qs
            .annotate(d=TruncDay('date')).values('d')
            .annotate(s=Sum('amount')).order_by('d')
        )
        rev_labels = [(today - timedelta(days=6 - i)).strftime('%a') for i in range(7)]
        rev_map = {r['d']: float(r['s'] or 0) for r in rev_rows}
        rev_values = [rev_map.get(today - timedelta(days=6 - i), 0) for i in range(7)]

    revenue_sum = income_total_qs.aggregate(s=Sum('amount'))['s'] or 0


    # Emergency trend

    from ipd.models import IPDAdmission
    emg_rows = (
        IPDAdmission.objects
        .filter(category='ICU', date__gte=today - timedelta(days=6))
        .annotate(d=TruncDay('date'))
        .values('d')
        .annotate(c=Count('id'))
        .order_by('d')
    )
    # TruncDay('date') gives a date object in Django values('d')
    emg_map = {r['d']: r['c'] for r in emg_rows}

    emg_values = [emg_map.get(today - timedelta(days=6 - i), 0) for i in range(7)]

    return Response({
        'range': range_filter,
        'expenses_timeseries': {
            'labels': labels,
            'values': values,
        },
        'patient_chart': {
            'labels': labels,
            'patient': counts,
            'trend': [max(0, c - 5) for c in counts],
            'patient_trends': [max(0, c - 8) for c in counts],
        },
        'patient_pie': {
            'old': old_patients if total_patients else 65,
            'new': new_patients if total_patients else 35,
        },
        'revenue': {
            'labels': rev_labels,
            'values': rev_values,
            'sum': float(revenue_sum),
        },
        'revenue_sum': float(revenue_sum),
        'emergency': {'values': emg_values},
    })


dashboard_stats.throttle_scope = 'dashboard'


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@throttle_classes([ScopedRateThrottle])
def dashboard_income_breakdown(request):
    """Income chart data for the dashboard: doctor fees, medicine
    charges, room charges by category (ICU/Private/General/Other),
    investigations, and a reconciling "Other Income" bucket.

    Hardening:
    - IsAuthenticated + scoped throttle (defense-in-depth on top of the
      project-wide REST_FRAMEWORK defaults).
    - `range` is validated against a whitelist before touching the ORM.
    - Result is cached briefly per range — this view runs half a dozen
      Sum() aggregations across OPD/Pharmacy/IPD/Income tables, so
      caching keeps a chatty dashboard (15s auto-refresh) from re-running
      that work on every poll.
    """
    range_filter = request.GET.get('range', 'today')
    if range_filter not in services.VALID_RANGES:
        range_filter = 'today'

    cache_key = f'dashboard:income_breakdown:{range_filter}'
    data = cache.get(cache_key)
    if data is None:
        try:
            data = services.get_income_breakdown(range_filter)
        except Exception:
            logger.exception('dashboard_income_breakdown failed for range=%s', range_filter)
            return Response(
                {'error': 'Unable to compute income breakdown right now.'},
                status=500,
            )
        cache.set(cache_key, data, timeout=30)

    return Response(data)


dashboard_income_breakdown.throttle_scope = 'dashboard'


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def patient_search(request):
    q = request.GET.get('q', '').strip()
    if not q:
        return Response({'results': []})
    # Cap query length: a patient name/uhid/mobile search never needs to
    # be longer than this, and an unbounded icontains() on an attacker
    # supplied string is a cheap way to pin down a DB worker.
    q = q[:100]
    patients = Patient.objects.filter(
        Q(name__icontains=q) | Q(uhid__icontains=q) | Q(mobile__icontains=q)
    )[:20]
    return Response({'results': [services.patient_to_dict(p) for p in patients]})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def uhid_lookup(request, uhid):
    try:
        p = Patient.objects.get(uhid=uhid)
        return Response(services.patient_to_dict(p))
    except Patient.DoesNotExist:
        return Response({'error': 'Not found'}, status=404)


@api_view(['GET'])
def ai_triage(request):
    from core.ai_services import triage_score

    category = request.GET.get('category', '')
    status = request.GET.get('status', '')
    diagnosis = request.GET.get('diagnosis', '')

    waiting_minutes_raw = request.GET.get('waiting_minutes', '0')
    try:
        waiting_minutes = int(waiting_minutes_raw)
    except ValueError:
        waiting_minutes = 0

    is_icu_raw = request.GET.get('is_icu', 'false').lower()
    is_icu = is_icu_raw in {'1', 'true', 'yes', 'y', 'on'}

    exp = triage_score(
        category=category,
        status=status,
        diagnosis_text=diagnosis,
        waiting_minutes=waiting_minutes,
        is_icu=is_icu,
    )
    return Response({'explanation': exp.to_dict()})


@api_view(['GET'])
def ai_prescription_summary(request):
    from core.ai_services import summarize_prescription
    text = request.GET.get('text', '')
    summary = summarize_prescription(text)
    return Response({'summary': summary})


@api_view(['GET'])
def ai_inventory_reorder(request):
    from core.ai_services import recommend_inventory_reorder

    def _to_float(v: str, default: Optional[float] = None):
        try:
            return float(v)
        except (TypeError, ValueError):
            return default

    def _to_int(v: str, default: int = 0):
        try:
            return int(v)
        except (TypeError, ValueError):
            return default

    stock = _to_int(request.GET.get('stock', '0'), 0)
    buffer = _to_int(request.GET.get('buffer', '0'), 0)
    unit = request.GET.get('unit', '')
    recent = _to_float(request.GET.get('recent_consumption_per_day', ''), None)
    lead_time_days = _to_int(request.GET.get('lead_time_days', '7'), 7)

    rec = recommend_inventory_reorder(
        stock=stock, buffer=buffer, unit=unit,
        recent_consumption_per_day=recent, lead_time_days=lead_time_days,
    )
    return Response({'recommendation': rec})


@api_view(['GET'])
def ai_lab_recommend(request):
    from core.ai_services import recommend_lab_tests
    diagnosis = request.GET.get('diagnosis', '')
    try:
        top_k = int(request.GET.get('top_k', '5'))
    except ValueError:
        top_k = 5
    results = recommend_lab_tests(diagnosis, top_k=top_k)
    return Response({'recommendations': results})