# Generated for ShantiVeer HMS — RBAC fix: add missing BillingClerk group.
#
# The BillingClerk role was defined in core/rbac.py from the start but the
# corresponding Django auth Group was never created in migration 0001.
# This migration creates the group and assigns the correct permissions so
# that billing staff can be assigned the role without requiring Admin access
# for every billing operation.

from django.apps import apps as global_apps
from django.contrib.auth.management import create_permissions
from django.db import migrations


BILLING_PERMISSIONS = [
    # Core billing operations — collect patient payments and view their bills
    ('ipd', 'ipdpayment',   ['view_ipdpayment', 'add_ipdpayment']),
    # Need to view admissions to look up the patient being billed
    ('ipd', 'ipdadmission', ['view_ipdadmission']),
    # Need to view OPD visits for billing purposes
    ('opd', 'opdvisit',     ['view_opdvisit']),
    # Income ledger — raise charges, post patient payments, TPA settlements
    ('income', 'incomeentry',  ['view_incomeentry', 'add_incomeentry']),
    ('income', 'ledgerentry',  ['view_ledgerentry', 'add_ledgerentry', 'change_ledgerentry']),
    # Expenses — view and record operational expenses
    ('expenses', 'expense',    ['view_expense', 'add_expense']),
    # Patient lookup — needed to find the patient being billed
    ('uhid', 'patient',        ['view_patient']),
]


def add_billingclerk_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    ContentType = apps.get_model('contenttypes', 'ContentType')

    # Ensure all referenced app permissions exist before querying them.
    app_labels = {app_label for app_label, _, _ in BILLING_PERMISSIONS}
    for app_label in app_labels:
        try:
            app_config = global_apps.get_app_config(app_label)
            create_permissions(app_config, apps=global_apps, verbosity=0)
        except LookupError:
            pass  # app not installed in this deployment — skip

    group, _ = Group.objects.get_or_create(name='BillingClerk')
    for app_label, model_name, codenames in BILLING_PERMISSIONS:
        try:
            ct = ContentType.objects.get(app_label=app_label, model=model_name)
        except ContentType.DoesNotExist:
            continue  # model not present in this deployment — skip safely
        perms = Permission.objects.filter(content_type=ct, codename__in=codenames)
        group.permissions.add(*perms)


def remove_billingclerk_group(apps, schema_editor):
    Group = apps.get_model('auth', 'Group')
    Group.objects.filter(name='BillingClerk').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_userprofile'),
        ('auth', '0012_alter_user_first_name_max_length'),
        ('contenttypes', '0002_remove_content_type_name'),
        ('ipd', '0001_initial'),
        ('opd', '0001_initial'),
        ('income', '0002_ledgerentry'),
        ('expenses', '0001_initial'),
        ('uhid', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(add_billingclerk_group, reverse_code=remove_billingclerk_group),
    ]
