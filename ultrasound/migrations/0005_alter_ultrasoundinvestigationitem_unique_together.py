from django.db import migrations


def deduplicate_usg_items(apps, schema_editor):
    """Remove duplicate (investigation, test) rows in UltrasoundInvestigationItem,
    keeping the first-created row and deleting later duplicates."""
    UltrasoundInvestigationItem = apps.get_model('ultrasound', 'UltrasoundInvestigationItem')

    seen = set()
    for item in UltrasoundInvestigationItem.objects.order_by('id'):
        key = (item.investigation_id, item.test_id)
        if key in seen:
            item.delete()
        else:
            seen.add(key)


class Migration(migrations.Migration):

    dependencies = [
        ('ultrasound', '0004_alter_ultrasoundinvestigation_options_and_more'),
    ]

    operations = [
        # Step 1: remove duplicate rows before enforcing uniqueness.
        migrations.RunPython(deduplicate_usg_items, migrations.RunPython.noop),
        # Step 2: add the unique_together constraint.
        migrations.AlterUniqueTogether(
            name='ultrasoundinvestigationitem',
            unique_together={('investigation', 'test')},
        ),
    ]
