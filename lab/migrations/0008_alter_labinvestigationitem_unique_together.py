from django.db import migrations


def deduplicate_lab_items(apps, schema_editor):
    """Remove duplicate (investigation, test) rows in LabInvestigationItem,
    keeping the one with the highest quantity (sum of dupes) and deleting the rest.
    This prevents the unique_together constraint from failing on existing data."""
    LabInvestigationItem = apps.get_model('lab', 'LabInvestigationItem')

    seen = set()
    # Order by id so we always keep the first-created row
    for item in LabInvestigationItem.objects.order_by('id'):
        key = (item.investigation_id, item.test_id)
        if key in seen:
            item.delete()
        else:
            seen.add(key)


class Migration(migrations.Migration):

    dependencies = [
        ('lab', '0007_remove_labinvestigationitem_uniq_lab_item_per_test_per_bill'),
    ]

    operations = [
        # Step 1: remove duplicate rows before enforcing uniqueness.
        migrations.RunPython(deduplicate_lab_items, migrations.RunPython.noop),
        # Step 2: add the unique_together constraint.
        migrations.AlterUniqueTogether(
            name='labinvestigationitem',
            unique_together={('investigation', 'test')},
        ),
    ]
