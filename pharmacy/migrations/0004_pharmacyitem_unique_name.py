from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pharmacy', '0003_historicalpharmacyitem_historicalpharmacypurchase'),
    ]

    operations = [
        migrations.AlterField(
            model_name='pharmacyitem',
            name='name',
            field=models.CharField(max_length=200, unique=True),
        ),
        migrations.AlterField(
            model_name='historicalpharmacyitem',
            name='name',
            field=models.CharField(max_length=200, db_index=True),
        ),
    ]
