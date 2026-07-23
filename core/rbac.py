"""
Centralized Role-Based Access Control for ShantiVeer HMS.

Encodes the module x role access matrix in one place so every app's
views, the sidebar, and the dashboard all agree on who can do what.

Access levels per module:
    'full' -> create / edit / delete / view
    'view' -> read-only
    'none' -> no access at all (sidebar link hidden, view returns 403)

Role keys correspond to Django Group names already created by
accounts/migrations/0001_create_hospital_groups.py.
"""
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from functools import wraps

ADMIN = 'Admin'
DOCTOR = 'Doctor'
RECEPTIONIST = 'Receptionist'
NURSE = 'Nurse'
LAB_TECH = 'LabTech'
PHARMACIST = 'Pharmacist'
BILLING = 'BillingClerk'
ACCOUNTANT = 'Accountant'

ALL_ROLES = [ADMIN, DOCTOR, RECEPTIONIST, NURSE, LAB_TECH, PHARMACIST, BILLING, ACCOUNTANT]


FULL, VIEW, NONE = 'full', 'view', 'none'

# Module key -> {role: level}. Any role missing from a module's dict
# defaults to NONE.
MODULE_ACCESS = {
'dashboard':         {ADMIN: FULL, DOCTOR: FULL, RECEPTIONIST: FULL, NURSE: FULL, LAB_TECH: FULL, PHARMACIST: FULL, BILLING: FULL, ACCOUNTANT: VIEW},
    'uhid':              {ADMIN: FULL, DOCTOR: VIEW, RECEPTIONIST: FULL, NURSE: VIEW,
                           LAB_TECH: VIEW, PHARMACIST: VIEW, BILLING: VIEW},
    # NOTE: the OPD app exposes a single combined queue+registration view,
    # so 'opd_registration' gates that screen for everyone who may see the
    # OPD queue at all; request.is_view_only hides the registration form
    # for roles that may only browse it (Doctor, Nurse).
    'opd_registration':  {ADMIN: FULL, DOCTOR: VIEW, RECEPTIONIST: FULL, NURSE: VIEW},
'opd_list':          {ADMIN: FULL, DOCTOR: FULL, RECEPTIONIST: FULL, NURSE: VIEW, ACCOUNTANT: FULL},
'ipd_admission':     {ADMIN: FULL, DOCTOR: FULL, RECEPTIONIST: FULL, NURSE: FULL, ACCOUNTANT: FULL},
    'ipd_list':          {ADMIN: FULL, DOCTOR: FULL, RECEPTIONIST: VIEW, NURSE: FULL, ACCOUNTANT: VIEW},
    'billing_collect':   {ADMIN: FULL, BILLING: FULL},
'patient_bill':      {ADMIN: FULL, DOCTOR: VIEW, BILLING: FULL, ACCOUNTANT: FULL},
    'discharge':         {ADMIN: FULL, DOCTOR: FULL, NURSE: VIEW},
    'lab':                {ADMIN: FULL, DOCTOR: FULL, NURSE: VIEW, LAB_TECH: FULL},
    'ultrasound':        {ADMIN: FULL, DOCTOR: FULL, NURSE: VIEW, LAB_TECH: FULL},
    'pharmacy':          {ADMIN: FULL, NURSE: VIEW, PHARMACIST: FULL},
    'prescription':      {ADMIN: FULL, DOCTOR: FULL, NURSE: VIEW, PHARMACIST: VIEW},
    'beds':              {ADMIN: FULL, DOCTOR: VIEW, RECEPTIONIST: VIEW, NURSE: FULL},
    'masterdata':        {ADMIN: FULL},
'income':            {ADMIN: FULL, BILLING: FULL, ACCOUNTANT: FULL},
'expenses':          {ADMIN: FULL, BILLING: FULL, ACCOUNTANT: FULL},

    # Accountant finance screens (Ledger/Reports/Receipts/etc.)


    'backup':            {ADMIN: FULL},
    'history':           {ADMIN: FULL},
    'django_admin':      {ADMIN: FULL},
}

ROLE_LABELS = {
    ADMIN: 'Administrator', DOCTOR: 'Doctor', RECEPTIONIST: 'Receptionist',
    NURSE: 'Nurse', LAB_TECH: 'Lab Technician', PHARMACIST: 'Pharmacist',
    BILLING: 'Billing Clerk',
}

ROLE_ICONS = {
    ADMIN: 'bi-shield-check', DOCTOR: 'bi-person-badge', RECEPTIONIST: 'bi-headset',
    NURSE: 'bi-heart-pulse', LAB_TECH: 'bi-droplet', PHARMACIST: 'bi-capsule',
    BILLING: 'bi-cash-coin',
}


def get_user_role(user):
    """Return the single primary role key for a user, or None."""
    if not user.is_authenticated:
        return None
    if user.is_superuser or (user.is_staff and not user.groups.exists()):
        return ADMIN
    group_names = set(user.groups.values_list('name', flat=True))
    if ADMIN in group_names:
        return ADMIN
    for role in ALL_ROLES:
        if role in group_names:
            return role
    return None


def get_access_level(user, module_key):
    """Return 'full' | 'view' | 'none' for this user on this module."""
    if not user.is_authenticated:
        return NONE
    if user.is_superuser:
        return FULL
    role = get_user_role(user)
    if role is None:
        return NONE
    return MODULE_ACCESS.get(module_key, {}).get(role, NONE)


def has_access(user, module_key, level=VIEW):
    """True if the user's access level for module_key is at least `level`."""
    current = get_access_level(user, module_key)
    if current == NONE:
        return False
    if level == VIEW:
        return current in (VIEW, FULL)
    return current == FULL


def require_module(module_key, level=VIEW):
    """View decorator enforcing the access matrix.

    level='view' -> user must have at least view access.
    level='full' -> user must have full (edit) access; used to guard
                     views that create/update/delete data.
    Also stamps request.is_view_only so templates can hide action
    buttons for users who only have read access to a 'full'-capable
    view (e.g. a combined list+create view shared across roles).
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped(request, *args, **kwargs):
            access = get_access_level(request.user, module_key)
            if access == NONE or (level == FULL and access != FULL):
                raise PermissionDenied(
                    f"Your role does not have access to this module.")
            request.is_view_only = (access == VIEW)
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator
