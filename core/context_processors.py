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


# Session key used to cache RBAC data — bump this string any time the
# access matrix changes so stale cached values are automatically evicted.
_RBAC_CACHE_VERSION = 'rbac_v1'
_RBAC_SESSION_KEY = f'_rbac_ctx_{_RBAC_CACHE_VERSION}'


def role_context(request):
    """Expose the user's RBAC role + per-module access map to every template.

    The role and access matrix are derived purely from the user's group
    membership, which changes very rarely. We cache the result in the
    session so the group DB query is only executed once per login session
    instead of on every single request.

    Cache is invalidated automatically when:
      - The user logs out (session is cleared).
      - The _RBAC_CACHE_VERSION constant is bumped (e.g. after an access
        matrix change or a deploy that alters group membership).
    """
    user = request.user
    if not user.is_authenticated:
        return {}

    # Try session cache first (avoids a DB round-trip on every page load).
    cached = request.session.get(_RBAC_SESSION_KEY)
    if cached is not None:
        return cached

    # Cache miss — compute from DB and store in the session.
    role = rbac.get_user_role(user)
    access = {
        key: rbac.get_access_level(user, key) for key in rbac.MODULE_ACCESS
    }
    ctx = {
        'user_role': role,
        'user_role_label': rbac.ROLE_LABELS.get(role, 'User'),
        'user_role_icon': rbac.ROLE_ICONS.get(role, 'bi-person'),
        'module_access': access,
    }

    # Persist to session so subsequent requests in this session skip the DB.
    request.session[_RBAC_SESSION_KEY] = ctx
    request.session.modified = True
    return ctx
