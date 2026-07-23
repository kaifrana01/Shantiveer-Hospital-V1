from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('expenses', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='expense',
            name='paid_to',
            field=models.CharField(
                blank=True,
                help_text='Person / party this amount was given to (e.g. staff name, vendor, patient).',
                max_length=150,
            ),
        ),
    ]
