"""
Lightweight JSON endpoints consumed by the admin dashboard widgets.
All views require staff login.
"""
import json
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import User, Group
from django.utils import timezone
from django.views.decorators.http import require_GET

from lab.models import LabTestMaster


def staff_required(fn):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_staff:
            return HttpResponseForbidden('Forbidden')
        return fn(request, *args, **kwargs)
    wrapper.__name__ = fn.__name__
    return wrapper


@require_GET
@staff_required
def admin_stats(request):
    today = timezone.localdate()
    return JsonResponse({
        'users':      User.objects.count(),
        'tests':      LabTestMaster.objects.filter(is_active=True).count(),
        'logs_today': LogEntry.objects.filter(action_time__date=today).count(),
        'groups':     Group.objects.count(),
    })


@require_GET
@staff_required
def admin_logs(request):
    logs = (
        LogEntry.objects
        .select_related('user', 'content_type')
        .order_by('-action_time')[:30]
    )
    data = []
    for entry in logs:
        local_time = timezone.localtime(entry.action_time)
        data.append({
            'date':        local_time.strftime('%d %b %Y'),
            'time':        local_time.strftime('%H:%M:%S'),
            'username':    entry.user.username,
            'user_name':   entry.user.get_full_name() or entry.user.username,
            'action_flag': entry.action_flag,
            'model':       entry.content_type.model.replace('_', ' ').title() if entry.content_type else '—',
            'object_repr': entry.object_repr[:80],
            'change_message': entry.get_change_message()[:120],
        })
    return JsonResponse(data, safe=False)


@require_GET
@staff_required
def admin_users(request):
    users = (
        User.objects
        .prefetch_related('groups')
        .order_by('-date_joined')[:20]
    )
    data = []
    for u in users:
        grps = list(u.groups.values_list('name', flat=True))
        role = grps[0] if grps else ('Superuser' if u.is_superuser else 'No Role')
        data.append({
            'id':        u.pk,
            'username':  u.username,
            'full_name': u.get_full_name(),
            'email':     u.email,
            'role':      role,
            'is_active': u.is_active,
            'is_staff':  u.is_staff,
            'date_joined': u.date_joined.strftime('%d %b %Y') if u.date_joined else '—',
        })
    return JsonResponse(data, safe=False)


@require_GET
@staff_required
def admin_tests(request):
    tests = LabTestMaster.objects.order_by('name')[:50]
    data = []
    for t in tests:
        data.append({
            'id':            t.pk,
            'name':          t.name,
            'rate':          str(t.rate),
            'is_active':     t.is_active,
            'history_count': t.history.count(),
        })
    return JsonResponse(data, safe=False)
