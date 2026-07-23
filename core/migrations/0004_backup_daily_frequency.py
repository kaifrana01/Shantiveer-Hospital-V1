from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_backup'),
    ]

    operations = [
        migrations.AlterField(
            model_name='backupschedule',
            name='frequency',
            field=models.CharField(
                choices=[
                    ('manual', 'Manual Only'),
                    ('daily', 'Daily'),
                    ('weekly', 'Weekly'),
                    ('monthly', 'Monthly'),
                    ('yearly', 'Yearly'),
                ],
                default='manual',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='backuprecord',
            name='backup_type',
            field=models.CharField(
                choices=[
                    ('manual', 'Manual'),
                    ('daily', 'Daily Auto'),
                    ('weekly', 'Weekly Auto'),
                    ('monthly', 'Monthly Auto'),
                    ('yearly', 'Yearly Auto'),
                ],
                default='manual',
                max_length=20,
            ),
        ),
    ]
