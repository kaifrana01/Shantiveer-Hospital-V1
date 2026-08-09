from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('masterdata', '0007_doctor_address_to_textfield'),
    ]

    operations = [
        migrations.AlterField(
            model_name='testinterpretation',
            name='test_name',
            field=models.CharField(max_length=300, unique=True),
        ),
        migrations.AlterField(
            model_name='historicaltestinterpretation',
            name='test_name',
            field=models.CharField(max_length=300, db_index=True),
        ),
    ]
