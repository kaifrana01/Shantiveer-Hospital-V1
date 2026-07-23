from django.contrib import admin

from .rbac import get_user_role, ROLE_ICONS, ROLE_LABELS


class HMSAdminSite(admin.AdminSite):
    site_header = 'ShantiVeer HMS Admin'

    def each_context(self, request):
        ctx = super().each_context(request)

        role = get_user_role(request.user) if request.user.is_authenticated else None
        ctx['user_role_label'] = ROLE_LABELS.get(role, '')
        ctx['user_role_icon'] = ROLE_ICONS.get(role, 'bi-person-badge')

        # Role-aware cards and module visibility for the admin landing.
        # We rely on the RBAC module access keys from core/rbac.py.
        cards = []
        visible_modules = set()

        if request.user.is_authenticated:
            from . import rbac

            def access_key(module_key):
                return rbac.get_access_level(request.user, module_key)

            def can(module_key):
                return access_key(module_key) in (rbac.VIEW, rbac.FULL)

            # Compute module visibility map for template gating.
            for mk in rbac.MODULE_ACCESS.keys():
                if can(mk):
                    visible_modules.add(mk)

            # Recommended/quick cards.
            if can('uhid'):
                cards.append({
                    'key': 'general',
                    'title': 'Patients (UHID)',
                    'desc': 'Patient master records & visits',
                    'icon': 'bi-people',
                    'url': '/uhid/',
                    'module_key': 'uhid',
                })

            if can('opd_list') or can('opd_registration'):
                cards.append({
                    'key': 'reception',
                    'title': 'OPD & Registrations',
                    'desc': 'OPD queue, registration & bills',
                    'icon': 'bi-person-plus',
                    'url': '/opd/',
                    'module_key': 'opd_list',
                })

            if can('ipd_list') or can('ipd_admission'):
                cards.append({
                    'key': 'doctor',
                    'title': 'IPD Admissions',
                    'desc': 'Inpatient care, payments & discharge',
                    'icon': 'bi-hospital',
                    'url': '/ipd/',
                    'module_key': 'ipd_list',
                })

            if can('lab'):
                cards.append({
                    'key': 'doctor',
                    'title': 'Lab Requests',
                    'desc': 'Investigations and reports',
                    'icon': 'bi-droplet',
                    'url': '/lab/',
                    'module_key': 'lab',
                })

            if can('pharmacy'):
                cards.append({
                    'key': 'pharma',
                    'title': 'Pharmacy',
                    'desc': 'Inventory, purchases & sales',
                    'icon': 'bi-capsule',
                    'url': '/pharmacy/',
                    'module_key': 'pharmacy',
                })

            if can('prescription'):
                cards.append({
                    'key': 'doctor',
                    'title': 'Prescriptions',
                    'desc': 'Doctor prescriptions & medication logs',
                    'icon': 'bi-file-medical',
                    'url': '/prescription/',
                    'module_key': 'prescription',
                })

            if can('beds'):
                cards.append({
                    'key': 'general',
                    'title': 'Bed Management',
                    'desc': 'Rooms, beds and occupancy',
                    'icon': 'bi-grid-3x2-gap',
                    'url': '/core/beds/',
                    'module_key': 'beds',
                })

        ctx['cards'] = cards
        # Used by the template to hide/show navigation items.
        ctx['visible_modules'] = visible_modules
        return ctx


