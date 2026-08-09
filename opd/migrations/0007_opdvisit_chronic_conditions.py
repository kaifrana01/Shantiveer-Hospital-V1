from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('opd', '0006_alter_historicalopdvisittestitem_created_at_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='opdvisit',
            name='chronic_conditions',
            field=models.TextField(blank=True, null=True, default=None, help_text='Chronic conditions noted at OPD registration.'),
        ),
        migrations.AddField(
            model_name='historicalopdvisit',
            name='chronic_conditions',
            field=models.TextField(blank=True, null=True, default=None, help_text='Chronic conditions noted at OPD registration.'),
        ),
    ]
