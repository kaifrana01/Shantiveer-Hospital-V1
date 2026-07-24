from django.conf import settings
from core import services
from core import rbac


def hospital_info(request):
    ctx = {
        'hospital_name':    settings.HOSPITAL_NAME,
        'hospital_address': settings.HOSPITAL_ADDRESS,
        'hospital_phone':   settings.HOSPITAL_PHONE,
        'hospital_upi_id':  getattr(settings, 'HOSPITAL_UPI_ID', ''),
    }
    if request.user.is_authenticated:
        ctx['unread_notifications'] = services.get_unread_notifications(request.user, limit=5)
        ctx['notification_count'] = services.get_unread_notification_count(request.user)
    else:
        ctx['unread_notifications'] = []
        ctx['notification_count'] = 0
    return ctx


def role_context(request):
    """Expose the user's RBAC role + a per-module access map to every
    template, so sidebars/buttons can adapt without each view having
    to pass this manually."""
    user = request.user
    if not user.is_authenticated:
        return {}
    role = rbac.get_user_role(user)
    access = {
        key: rbac.get_access_level(user, key) for key in rbac.MODULE_ACCESS
    }
    return {
        'user_role': role,
        'user_role_label': rbac.ROLE_LABELS.get(role, 'User'),
        'user_role_icon': rbac.ROLE_ICONS.get(role, 'bi-person'),
        'module_access': access,
    }
