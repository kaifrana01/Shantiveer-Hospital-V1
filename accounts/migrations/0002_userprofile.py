from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_create_hospital_groups'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='UserProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('phone', models.CharField(blank=True, max_length=15)),
                ('alternate_phone', models.CharField(blank=True, max_length=15)),
                ('date_of_birth', models.DateField(blank=True, null=True)),
                ('gender', models.CharField(blank=True, choices=[('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other')], max_length=10)),
                ('blood_group', models.CharField(blank=True, choices=[('A+', 'A+'), ('A-', 'A-'), ('B+', 'B+'), ('B-', 'B-'), ('AB+', 'AB+'), ('AB-', 'AB-'), ('O+', 'O+'), ('O-', 'O-')], max_length=5)),
                ('address', models.TextField(blank=True)),
                ('emergency_contact', models.CharField(blank=True, max_length=100)),
                ('profile_photo', models.ImageField(blank=True, null=True, upload_to='profile_photos/')),
                ('designation', models.CharField(blank=True, max_length=100)),
                ('department', models.CharField(blank=True, max_length=100)),
                ('specialization', models.CharField(blank=True, max_length=100)),
                ('qualification', models.CharField(blank=True, max_length=200)),
                ('employee_code', models.CharField(blank=True, max_length=50)),
                ('joining_date', models.DateField(blank=True, null=True)),
                ('username_handle', models.CharField(blank=True, help_text='e.g. @mchdkaif', max_length=60)),
                ('document_1', models.FileField(blank=True, null=True, upload_to='profile_docs/')),
                ('document_1_name', models.CharField(blank=True, max_length=100)),
                ('document_2', models.FileField(blank=True, null=True, upload_to='profile_docs/')),
                ('document_2_name', models.CharField(blank=True, max_length=100)),
                ('document_3', models.FileField(blank=True, null=True, upload_to='profile_docs/')),
                ('document_3_name', models.CharField(blank=True, max_length=100)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='profile', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
