from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import PermissionDenied
from core.rbac import require_module


@require_module('django_admin', level='full')
def admin_console(request):
    """SPA-like admin console UI (users/tests/logs).
    Restricted to Admin role only — same gate as the Django admin itself.
    The underlying JSON endpoints (core.admin_api) additionally require is_staff.
    """
    return render(request, 'core/admin_console.html', {
        'active_sidebar': 'dashboard',
    })
