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

    BUG-08 FIX: to handle mid-session role changes (e.g. Admin promotes a
    Nurse to Doctor while both are logged in), we store a group-membership
    checksum alongside the cached data.  On each request we compare the
    current groups against the checksum.  If they differ — the role changed —
    we bust the cache and recompute.  This adds one cheap VALUES query per
    request (just group PKs, no joins) instead of the full group name fetch,
    which is a good tradeoff.

    Cache is also invalidated automatically when:
      - The user logs out (session is cleared).
      - The _RBAC_CACHE_VERSION constant is bumped (e.g. after an access
        matrix change or a deploy that alters group membership).
    """
    user = request.user
    if not user.is_authenticated:
        return {}

    # Compute a stable, cross-process checksum of the user's current group PKs.
    # We use a sorted tuple of integer PKs rather than hash() because Python's
    # hash() is randomised per-process (PYTHONHASHSEED), so a hash stored in a
    # session from one worker would never match one computed in another worker.
    # Sorted tuple comparison is O(n) on a tiny list and perfectly stable.
    current_group_pks = tuple(sorted(user.groups.values_list('id', flat=True)))

    # Try session cache first (avoids a DB round-trip on every page load).
    cached = request.session.get(_RBAC_SESSION_KEY)
    if cached is not None:
        # Validate against current group membership — bust cache if changed.
        if cached.get('_group_pks') == list(current_group_pks):
            # Return a copy without the internal checksum key.
            return {k: v for k, v in cached.items() if k != '_group_pks'}
        # Groups changed mid-session — fall through to recompute below.

    # Cache miss or stale — compute from DB and store in the session.
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

    # Persist to session (store sorted PKs list for cross-process stability).
    request.session[_RBAC_SESSION_KEY] = dict(ctx, _group_pks=list(current_group_pks))
    request.session.modified = True
    return ctx
