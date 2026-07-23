from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import simple_history.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('uhid', '0002_historicalpatient'),
    ]

    operations = [
        migrations.CreateModel(
            name='UltrasoundTestMaster',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=200, unique=True)),
                ('rate', models.DecimalField(decimal_places=2, max_digits=10)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={
                'verbose_name': 'Ultrasound Test',
                'verbose_name_plural': 'Ultrasound Tests',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='UltrasoundInvestigation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('bill_no', models.CharField(editable=False, max_length=20, unique=True)),
                ('patient_name', models.CharField(max_length=200)),
                ('mobile', models.CharField(blank=True, max_length=15)),
                ('address', models.TextField(blank=True)),
                ('consultant', models.CharField(default='-- Self --', max_length=200)),
                ('referred_by', models.CharField(default='SELF', max_length=200)),
                ('remarks', models.TextField(blank=True)),
                ('total', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('discount', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('payment_mode', models.CharField(default='Cash', max_length=20)),
                ('test_date', models.DateField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('patient', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='ultrasound_bills', to='uhid.patient')),
            ],
            options={
                'ordering': ['-test_date'],
            },
        ),
        migrations.CreateModel(
            name='UltrasoundInvestigationItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rate', models.DecimalField(decimal_places=2, max_digits=10)),
                ('quantity', models.PositiveIntegerField(default=1)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('investigation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='ultrasound.ultrasoundinvestigation')),
                ('test', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='ultrasound.ultrasoundtestmaster')),
            ],
        ),
        migrations.CreateModel(
            name='UltrasoundDocument',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to='ultrasound_documents/%Y/%m/')),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('investigation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='documents', to='ultrasound.ultrasoundinvestigation')),
            ],
        ),
        migrations.CreateModel(
            name='HistoricalUltrasoundTestMaster',
            fields=[
                ('id', models.BigIntegerField(auto_created=True, blank=True, db_index=True, verbose_name='ID')),
                ('name', models.CharField(db_index=True, max_length=200)),
                ('rate', models.DecimalField(decimal_places=2, max_digits=10)),
                ('is_active', models.BooleanField(default=True)),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField(db_index=True)),
                ('history_change_reason', models.CharField(max_length=100, null=True)),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('history_user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'historical Ultrasound Test',
                'verbose_name_plural': 'historical Ultrasound Tests',
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': ('history_date', 'history_id'),
            },
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),
        migrations.CreateModel(
            name='HistoricalUltrasoundInvestigationItem',
            fields=[
                ('id', models.BigIntegerField(auto_created=True, blank=True, db_index=True, verbose_name='ID')),
                ('rate', models.DecimalField(decimal_places=2, max_digits=10)),
                ('quantity', models.PositiveIntegerField(default=1)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField(db_index=True)),
                ('history_change_reason', models.CharField(max_length=100, null=True)),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('history_user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('investigation', models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='ultrasound.ultrasoundinvestigation')),
                ('test', models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='ultrasound.ultrasoundtestmaster')),
            ],
            options={
                'verbose_name': 'historical ultrasound investigation item',
                'verbose_name_plural': 'historical ultrasound investigation items',
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': ('history_date', 'history_id'),
            },
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),
        migrations.CreateModel(
            name='HistoricalUltrasoundInvestigation',
            fields=[
                ('id', models.BigIntegerField(auto_created=True, blank=True, db_index=True, verbose_name='ID')),
                ('bill_no', models.CharField(db_index=True, editable=False, max_length=20)),
                ('patient_name', models.CharField(max_length=200)),
                ('mobile', models.CharField(blank=True, max_length=15)),
                ('address', models.TextField(blank=True)),
                ('consultant', models.CharField(default='-- Self --', max_length=200)),
                ('referred_by', models.CharField(default='SELF', max_length=200)),
                ('remarks', models.TextField(blank=True)),
                ('total', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('discount', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('payment_mode', models.CharField(default='Cash', max_length=20)),
                ('test_date', models.DateField()),
                ('created_at', models.DateTimeField(blank=True, editable=False)),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField(db_index=True)),
                ('history_change_reason', models.CharField(max_length=100, null=True)),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('history_user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('patient', models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='uhid.patient')),
            ],
            options={
                'verbose_name': 'historical ultrasound investigation',
                'verbose_name_plural': 'historical ultrasound investigations',
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': ('history_date', 'history_id'),
            },
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),
        migrations.CreateModel(
            name='HistoricalUltrasoundDocument',
            fields=[
                ('id', models.BigIntegerField(auto_created=True, blank=True, db_index=True, verbose_name='ID')),
                ('file', models.TextField(max_length=100)),
                ('uploaded_at', models.DateTimeField(blank=True, editable=False)),
                ('history_id', models.AutoField(primary_key=True, serialize=False)),
                ('history_date', models.DateTimeField(db_index=True)),
                ('history_change_reason', models.CharField(max_length=100, null=True)),
                ('history_type', models.CharField(choices=[('+', 'Created'), ('~', 'Changed'), ('-', 'Deleted')], max_length=1)),
                ('history_user', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('investigation', models.ForeignKey(blank=True, db_constraint=False, null=True, on_delete=django.db.models.deletion.DO_NOTHING, related_name='+', to='ultrasound.ultrasoundinvestigation')),
            ],
            options={
                'verbose_name': 'historical ultrasound document',
                'verbose_name_plural': 'historical ultrasound documents',
                'ordering': ('-history_date', '-history_id'),
                'get_latest_by': ('history_date', 'history_id'),
            },
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),
    ]
