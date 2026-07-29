"""
Activity History module.

Reads django-simple-history tables across every app and renders a
searchable "who changed what, and when" timeline.

Performance notes:
  - Default view is scoped to the last 7 days to keep queries fast.
  - diff_fields is computed lazily only on the paginated page, not the
    full result set, eliminating the N+1 prev_record query.
  - Each historical model query is limited and only fired when its
    model_key matches the active filter (or no model filter is set).
"""
from django.apps import apps as django_apps
import datetime
from django.core.paginator import Paginator
from django.shortcuts import render
from django.utils import timezone

from core.rbac import require_module


ACTION_LABELS = {'+': 'Created', '~': 'Updated', '-': 'Deleted'}
ACTION_BADGE  = {'+': 'success',  '~': 'warning',  '-': 'danger'}

# Per-model cap — keeps each query bounded.
PER_MODEL_LIMIT = 200
# Overall cap after merging all models.
TOTAL_LIMIT = 500
# Default lookback window (days) when no date filter is given.
DEFAULT_DAYS = 7


def _get_historical_models():
    """Every concrete model wired up with django-simple-history's
    HistoricalRecords, discovered dynamically."""
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
    """Safe string for history timeline — guards against DoesNotExist
    when a related object was deleted after the history entry was written."""
    try:
        return str(rec)
    except Exception:
        return f"{rec.__class__.__name__} (id={getattr(rec, 'id', '?')})"


def _diff_fields(model, record):
    """Field-level changes for an Updated record vs its previous version.
    Called only on the small paginated slice, not the full result set.
    """
    if record['action_code'] != '~':
        return []
    rec = record['_raw']
    prev = rec.prev_record          # one extra query — acceptable on ~30 rows
    if prev is None:
        return []
    try:
        delta = rec.diff_against(prev)
    except Exception:
        return []
    changes = []
    for change in delta.changes:
        try:
            field_obj = model._meta.get_field(change.field)
            label = str(field_obj.verbose_name).title()
        except Exception:
            label = change.field.replace('_', ' ').title()
        changes.append({'field': label, 'old': change.old, 'new': change.new})
    return changes


@require_module('history', level='view')
def activity_log(request):
    model_filter  = request.GET.get('model',  '').strip()
    user_filter   = request.GET.get('user',   '').strip()
    action_filter = request.GET.get('action', '').strip()

    def _safe_date(raw):
        if not raw:
            return ''
        try:
            datetime.date.fromisoformat(raw.strip())
            return raw.strip()
        except (ValueError, AttributeError):
            return ''

    date_from = _safe_date(request.GET.get('date_from', ''))
    date_to   = _safe_date(request.GET.get('date_to',   ''))

    # Default to last 7 days when no date filter is given — prevents a
    # full-table scan across every historical model on each page load.
    using_default_range = not date_from and not date_to
    if using_default_range:
        date_from = str(timezone.localdate() - datetime.timedelta(days=DEFAULT_DAYS - 1))

    historical_models = _get_historical_models()
    model_choices = sorted(
        {(f"{app}.{name}", model._meta.verbose_name.title())
         for app, name, model, hist in historical_models},
        key=lambda pair: pair[1],
    )

    all_records = []
    # Map model_key -> model object for diff_fields lookup later.
    model_by_key: dict = {}

    for app_label, model_name, model, hist_model in historical_models:
        model_key = f"{app_label}.{model_name}"
        if model_filter and model_filter != model_key:
            continue

        model_by_key[model_key] = model

        qs = hist_model.objects.all()

        # Always filter by date — the most selective filter, uses the
        # history_date index that simple-history creates automatically.
        if date_from:
            qs = qs.filter(history_date__date__gte=date_from)
        if date_to:
            qs = qs.filter(history_date__date__lte=date_to)
        if action_filter:
            qs = qs.filter(history_type=action_filter)
        if user_filter:
            qs = qs.filter(history_user__username__icontains=user_filter)

        # select_related avoids a per-row JOIN for history_user.
        qs = qs.select_related('history_user').order_by('-history_date')[:PER_MODEL_LIMIT]

        pk_attr = model._meta.pk.attname
        for rec in qs:
            local_dt = timezone.localtime(rec.history_date)
            all_records.append({
                'model_name':  model._meta.verbose_name.title(),
                'model_key':   model_key,
                'object_id':   getattr(rec, pk_attr, None),
                'object_repr': _safe_object_repr(rec)[:80],
                'action':      ACTION_LABELS.get(rec.history_type, rec.history_type),
                'action_code': rec.history_type,
                'badge':       ACTION_BADGE.get(rec.history_type, 'secondary'),
                'username':    rec.history_user.username if rec.history_user else 'System',
                'full_name':   (rec.history_user.get_full_name() if rec.history_user else '') or '',
                'reason':      getattr(rec, 'history_change_reason', '') or '',
                'date':        local_dt.strftime('%d %b %Y'),
                'time':        local_dt.strftime('%H:%M:%S'),
                'timestamp':   rec.history_date,
                # Keep raw record only for diff — dropped after pagination.
                '_raw':        rec,
            })

    all_records.sort(key=lambda r: r['timestamp'], reverse=True)
    all_records = all_records[:TOTAL_LIMIT]

    paginator = Paginator(all_records, 30)
    page_obj  = paginator.get_page(request.GET.get('page'))

    # Compute field diffs only for the current page (~30 rows max) to
    # avoid the N+1 prev_record query running on hundreds of records.
    for record in page_obj.object_list:
        model = model_by_key.get(record['model_key'])
        record['changes'] = _diff_fields(model, record) if model else []
        del record['_raw']  # don't pass ORM objects to the template

    context = {
        'active_sidebar':    'history',
        'page_obj':          page_obj,
        'model_choices':     model_choices,
        'action_choices':    [('+', 'Created'), ('~', 'Updated'), ('-', 'Deleted')],
        'using_default_range': using_default_range,
        'default_days':      DEFAULT_DAYS,
        'filters': {
            'model':     model_filter,
            'user':      user_filter,
            'action':    action_filter,
            'date_from': date_from if not using_default_range else '',
            'date_to':   date_to,
        },
        'total_count': len(all_records),
    }
    return render(request, 'history/activity_log.html', context)
