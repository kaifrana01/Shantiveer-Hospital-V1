from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('expenses', '0002_expense_paid_to'),
    ]

    operations = [
        migrations.AddField(
            model_name='expense',
            name='batch_id',
            field=models.UUIDField(
                blank=True,
                db_index=True,
                help_text='Groups rows created together in a single form submission so they render as one table row.',
                null=True,
            ),
        ),
    ]
