from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_notification'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='BackupSchedule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('frequency', models.CharField(
                    choices=[('manual', 'Manual Only'), ('weekly', 'Weekly'), ('monthly', 'Monthly'), ('yearly', 'Yearly')],
                    default='manual', max_length=20,
                )),
                ('is_active', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'verbose_name': 'Backup Schedule'},
        ),
        migrations.CreateModel(
            name='BackupRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('filename', models.CharField(max_length=300)),
                ('filepath', models.CharField(max_length=500)),
                ('size_bytes', models.BigIntegerField(default=0)),
                ('backup_type', models.CharField(
                    choices=[('manual', 'Manual'), ('weekly', 'Weekly Auto'), ('monthly', 'Monthly Auto'), ('yearly', 'Yearly Auto')],
                    default='manual', max_length=20,
                )),
                ('status', models.CharField(
                    choices=[('success', 'Success'), ('failed', 'Failed'), ('in_progress', 'In Progress')],
                    default='in_progress', max_length=20,
                )),
                ('error_message', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]