# Generated for ShantiVeer HMS — Phase 1: RBAC group setup.
#
# Creates the standard hospital role groups and wires them to the
# *actual* model permissions in this codebase (not placeholder names),
# so a fresh deployment has working RBAC out of the box instead of
# requiring an admin to click through the Django admin manually.

from django.apps import apps as global_apps
from django.contrib.auth.management import create_permissions
from django.db import migrations


# Each group maps to (app_label, model_name, [permission codenames]).
# Codenames follow Django's default add_/change_/delete_/view_<model> scheme.
GROUP_PERMISSIONS = {
    'Doctor': [
        ('opd', 'opdvisit', ['view_opdvisit', 'add_opdvisit', 'change_opdvisit']),
        ('ipd', 'ipdadmission', ['view_ipdadmission', 'add_ipdadmission', 'change_ipdadmission']),
        ('ipd', 'dischargesummary', ['view_dischargesummary', 'add_dischargesummary', 'change_dischargesummary']),
        ('prescription', 'prescription', ['view_prescription', 'add_prescription', 'change_prescription']),
        ('lab', 'labinvestigation', ['view_labinvestigation']),
        ('uhid', 'patient', ['view_patient', 'add_patient', 'change_patient']),
    ],
    'Nurse': [
        ('ipd', 'ipdadmission', ['view_ipdadmission', 'change_ipdadmission']),
        ('ipd', 'ipdmedicineline', ['view_ipdmedicineline', 'add_ipdmedicineline']),
        ('core', 'bed', ['view_bed', 'change_bed']),
        ('uhid', 'patient', ['view_patient']),
    ],
    'Receptionist': [
        ('uhid', 'patient', ['view_patient', 'add_patient', 'change_patient']),
        ('opd', 'opdvisit', ['view_opdvisit', 'add_opdvisit']),
        ('ipd', 'ipdadmission', ['view_ipdadmission', 'add_ipdadmission']),
        ('core', 'bed', ['view_bed']),
    ],
    'Pharmacist': [
        ('pharmacy', 'pharmacyitem', ['view_pharmacyitem', 'add_pharmacyitem', 'change_pharmacyitem']),
        ('pharmacy', 'pharmacypurchase', ['view_pharmacypurchase', 'add_pharmacypurchase']),
        ('pharmacy', 'pharmacysale', ['view_pharmacysale', 'add_pharmacysale']),
        ('prescription', 'prescription', ['view_prescription']),
    ],
    'LabTech': [
        ('lab', 'labtestmaster', ['view_labtestmaster']),
        ('lab', 'labinvestigation', ['view_labinvestigation', 'add_labinvestigation', 'change_labinvestigation']),
        ('lab', 'labinvestigationitem', ['view_labinvestigationitem', 'add_labinvestigationitem', 'change_labinvestigationitem']),
        ('lab', 'labtestresult', ['view_labtestresult', 'add_labtestresult', 'change_labtestresult']),
    ],
    'Accountant': [
        ('ipd', 'ipdpayment', ['view_ipdpayment', 'add_ipdpayment']),
        ('opd', 'opdvisit', ['view_opdvisit', 'change_opdvisit']),
        ('pharmacy', 'pharmacysale', ['view_pharmacysale', 'add_pharmacysale']),
        ('income', 'incomeentry', ['view_incomeentry', 'add_incomeentry']),
        # The single ledger (Phase 2/3) is the billing desk's core tool:
        # raising charges, collecting patient payments, and posting TPA
        # settlements all happen here.
        ('income', 'ledgerentry', ['view_ledgerentry', 'add_ledgerentry', 'change_ledgerentry']),
    ],
    # 'Accountant': [
    #     # View finance + billing data; no add/change/delete.
    #     ('income', 'incomeentry', ['view_incomeentry']),
    #     ('income', 'ledgerentry', ['view_ledgerentry']),
    #     ('expenses', 'expense', ['view_expense']),
    #     ('opd', 'opdvisit', ['view_opdvisit']),
    #     ('ipd', 'ipdadmission', ['view_ipdadmission']),
    #     ('lab', 'labinvestigation', ['view_labinvestigation']),
    #     ('ultrasound', 'ultrasoundinvestigation', ['view_ultrasoundinvestigation']),
    # ],

    'BillingClerk': [
        # Billing clerks handle patient payments and basic financial operations
        ('ipd', 'ipdpayment', ['view_ipdpayment', 'add_ipdpayment']),
        ('opd', 'opdvisit', ['view_opdvisit']),
        ('ipd', 'ipdadmission', ['view_ipdadmission']),
        ('income', 'incomeentry', ['view_incomeentry', 'add_incomeentry']),
        ('income', 'ledgerentry', ['view_ledgerentry', 'add_ledgerentry', 'change_ledgerentry']),
        ('expenses', 'expense', ['view_expense', 'add_expense']),
        ('uhid', 'patient', ['view_patient']),
    ],

    'Admin': [
        # Admins get full CRUD across every financially or clinically

        # sensitive model. (Superusers bypass permission checks entirely,
        # but this group lets you grant "Admin-level" access to a
        # non-superuser account too, e.g. a hospital administrator who
        # shouldn't have Django-admin-level system access.)
        ('uhid', 'patient', ['view_patient', 'add_patient', 'change_patient', 'delete_patient']),
        ('opd', 'opdvisit', ['view_opdvisit', 'add_opdvisit', 'change_opdvisit', 'delete_opdvisit']),
        ('ipd', 'ipdadmission', ['view_ipdadmission', 'add_ipdadmission', 'change_ipdadmission', 'delete_ipdadmission']),
        ('ipd', 'ipdpayment', ['view_ipdpayment', 'add_ipdpayment', 'change_ipdpayment', 'delete_ipdpayment']),
        ('lab', 'labinvestigation', ['view_labinvestigation', 'add_labinvestigation', 'change_labinvestigation', 'delete_labinvestigation']),
        ('pharmacy', 'pharmacysale', ['view_pharmacysale', 'add_pharmacysale', 'change_pharmacysale', 'delete_pharmacysale']),
        ('income', 'incomeentry', ['view_incomeentry', 'add_incomeentry', 'change_incomeentry', 'delete_incomeentry']),
        ('income', 'ledgerentry', ['view_ledgerentry', 'add_ledgerentry', 'change_ledgerentry', 'delete_ledgerentry']),
    ],
}


def create_hospital_groups(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    ContentType = apps.get_model('contenttypes', 'ContentType')

    # Ensure permissions for content types referenced by GROUP_PERMISSIONS exist.
    # (This migration runs mid-plan; Django post_migrate signals may not have
    # created permissions for every app yet.)

    # Django normally creates each model's add_/change_/delete_/view_
    # Permission rows via a post_migrate signal — but that signal only
    # fires once the *entire* migration plan finishes, not after each
    # app. Since this data migration runs mid-plan, we must trigger
    # permission creation ourselves for every app we're about to grant
    # permissions from, or the queries below silently return nothing.
    app_labels = {app_label for mappings in GROUP_PERMISSIONS.values()
                  for app_label, _, _ in mappings}
    for app_label in app_labels:
        app_config = global_apps.get_app_config(app_label)
        create_permissions(app_config, apps=global_apps, verbosity=0)

    # Also: for already-existing groups from prior runs/versions,
    # ensure newly added role(s) like "Accountant" get their permissions.
    #
    # This keeps the database consistent even if the role group was
    # added after the migration was first applied.


    for group_name, mappings in GROUP_PERMISSIONS.items():
        group, _ = Group.objects.get_or_create(name=group_name)
        for app_label, model_name, codenames in mappings:
            try:
                ct = ContentType.objects.get(app_label=app_label, model=model_name)
            except ContentType.DoesNotExist:
                # Safeguard: if a model/app doesn't exist yet in this
                # deployment (e.g. migrations applied out of order),
                # skip it rather than failing the whole migration.
                continue
            perms = Permission.objects.filter(content_type=ct, codename__in=codenames)
            group.permissions.add(*perms)


def remove_hospital_groups(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name__in=GROUP_PERMISSIONS.keys()).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('contenttypes', '0002_remove_content_type_name'),
        ('uhid', '0001_initial'),
        ('opd', '0001_initial'),
        ('ipd', '0001_initial'),
        ('lab', '0001_initial'),
        ('pharmacy', '0001_initial'),
        ('prescription', '0001_initial'),
        ('income', '0002_ledgerentry'),
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_hospital_groups, reverse_code=remove_hospital_groups),
    ]
