from django.shortcuts import render
from django.contrib.auth.decorators import login_required


@login_required
def admin_console(request):
    # Render a SPA-like admin console UI (users/tests/logs). The UI uses the
    # existing JSON endpoints exposed by core.admin_api.
    return render(request, 'core/admin_console.html', {
        'active_sidebar': 'dashboard',
    })

