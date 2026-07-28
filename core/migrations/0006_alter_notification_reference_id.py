from django.db import migrations, models


def nullify_empty_reference_ids(apps, schema_editor):
    """Convert empty-string reference_id values to NULL before applying
    the unique constraint — MySQL treats multiple empty strings as duplicate
    unique values, but multiple NULLs are allowed."""
    Notification = apps.get_model('core', 'Notification')
    Notification.objects.filter(reference_id='').update(reference_id=None)


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_historicalbed'),
    ]

    operations = [
        # Step 1: convert '' → NULL so the unique constraint doesn't collide.
        migrations.RunPython(nullify_empty_reference_ids, migrations.RunPython.noop),
        # Step 2: alter the field to null=True, unique=True.
        migrations.AlterField(
            model_name='notification',
            name='reference_id',
            field=models.CharField(
                blank=True, default=None,
                help_text='Unique key to prevent duplicate alerts. NULL = no dedup needed.',
                max_length=50, null=True, unique=True,
            ),
        ),
    ]
