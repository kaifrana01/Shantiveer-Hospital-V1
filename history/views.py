"""
Activity History module.

Every record-keeping model across ShantiVeer HMS (Patient/UHID, OPD, IPD,
Lab, Ultrasound, Pharmacy, Income, Expenses, ...) is already tracked by
django-simple-history (see `history = HistoricalRecords()` on each model
and `simple_history.middleware.HistoryRequestMiddleware` in MIDDLEWARE,
which stamps every change with the logged-in user automatically).

This app does not duplicate that tracking — it simply reads the existing
historical tables across every app and renders a single, searchable,
human-readable "who changed what, and when" timeline.
"""
from django.apps import apps as django_apps
import datetime
from django.core.paginator import Paginator
from django.shortcuts import render
from django.utils import timezone

from core.rbac import require_module


ACTION_LABELS = {'+': 'Created', '~': 'Updated', '-': 'Deleted'}
ACTION_BADGE = {'+': 'success', '~': 'warning', '-': 'danger'}

# Per-model and overall caps so the timeline stays fast even with a lot
# of history accumulated over time. Filters narrow this down further.
PER_MODEL_LIMIT = 300
TOTAL_LIMIT = 1000


def _get_historical_models():
    """Every concrete model wired up with django-simple-history's
    HistoricalRecords, discovered dynamically (so newly added modules
    show up here automatically, with no extra wiring needed)."""
    results = []
    for model in django_apps.get_models():
        history_manager = getattr(model, 'history', None)
        if history_manager is None:
            continue
        try:
            hist_model = model.history.model
        except Exception:
            continue
        if model._meta.app_label == 'history':
            continue
        results.append((model._meta.app_label, model._meta.model_name, model, hist_model))
    return results


def _safe_object_repr(rec):
    """Return a safe string for history timeline.

    django-simple-history models often rely on __str__ of the original model.
    If the related object was deleted, those __str__ methods can raise
    DoesNotExist.
    """
    try:
        return str(rec)
    except Exception:
        return f"{rec.__class__.__name__} (id={getattr(rec, 'id', None)})"


def _diff_fields(model, record):
    """Field-level changes for an 'Updated' record, compared to the
    previous version of the same row. Returns [{field, old, new}, ...]."""
    changes = []
    prev = record.prev_record
    if prev is None:
        return changes
    try:
        delta = record.diff_against(prev)
    except Exception:
        return changes
    for change in delta.changes:
        try:
            field_obj = model._meta.get_field(change.field)
            label = field_obj.verbose_name
            label = str(label).title() if label else change.field
        except Exception:
            label = change.field.replace('_', ' ').title()
        changes.append({'field': label, 'old': change.old, 'new': change.new})
    return changes


@require_module('history', level='view')
def activity_log(request):
    model_filter = request.GET.get('model', '').strip()
    user_filter = request.GET.get('user', '').strip()
    action_filter = request.GET.get('action', '').strip()

    # Validate date inputs — invalid strings would cause ORM exceptions
    def _safe_date(raw):
        if not raw:
            return ''
        try:
            datetime.date.fromisoformat(raw.strip())
            return raw.strip()
        except (ValueError, AttributeError):
            return ''

    date_from = _safe_date(request.GET.get('date_from', ''))
    date_to = _safe_date(request.GET.get('date_to', ''))

    historical_models = _get_historical_models()
    model_choices = sorted(
        {(f"{app}.{name}", model._meta.verbose_name.title())
         for app, name, model, hist in historical_models},
        key=lambda pair: pair[1]
    )

    all_records = []
    for app_label, model_name, model, hist_model in historical_models:
        model_key = f"{app_label}.{model_name}"
        if model_filter and model_filter != model_key:
            continue

        qs = hist_model.objects.all()
        if action_filter:
            qs = qs.filter(history_type=action_filter)
        if user_filter:
            qs = qs.filter(history_user__username__icontains=user_filter)
        if date_from:
            qs = qs.filter(history_date__date__gte=date_from)
        if date_to:
            qs = qs.filter(history_date__date__lte=date_to)

        qs = qs.select_related('history_user').order_by('-history_date')[:PER_MODEL_LIMIT]

        pk_attr = model._meta.pk.attname
        for rec in qs:
            local_dt = timezone.localtime(rec.history_date)
            all_records.append({
                'model_name': model._meta.verbose_name.title(),
                'model_key': model_key,
                'object_id': getattr(rec, pk_attr, None),
                # simple-history can crash rendering __str__ for HistoricalRecords
                # when the related object was deleted (e.g. OPDVisitTestItem refers
                # to an OPDVisit that no longer exists).
                # Always guard stringification for history timeline.
                'object_repr': _safe_object_repr(rec)[:80],
                'action': ACTION_LABELS.get(rec.history_type, rec.history_type),
                'action_code': rec.history_type,
                'badge': ACTION_BADGE.get(rec.history_type, 'secondary'),
                'username': rec.history_user.username if rec.history_user else 'System',
                'full_name': (rec.history_user.get_full_name() if rec.history_user else '') or '',
                'reason': getattr(rec, 'history_change_reason', '') or '',
                'date': local_dt.strftime('%d %b %Y'),
                'time': local_dt.strftime('%H:%M:%S'),
                'timestamp': rec.history_date,
                'changes': _diff_fields(model, rec) if rec.history_type == '~' else [],
            })

    all_records.sort(key=lambda r: r['timestamp'], reverse=True)
    all_records = all_records[:TOTAL_LIMIT]

    paginator = Paginator(all_records, 30)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'active_sidebar': 'history',
        'page_obj': page_obj,
        'model_choices': model_choices,
        'action_choices': [('+', 'Created'), ('~', 'Updated'), ('-', 'Deleted')],
        'filters': {
            'model': model_filter,
            'user': user_filter,
            'action': action_filter,
            'date_from': date_from,
            'date_to': date_to,
        },
        'total_count': len(all_records),
    }
    return render(request, 'history/activity_log.html', context)
