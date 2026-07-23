from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ultrasound', '0002_delete_historicalultrasounddocument'),
    ]

    operations = [
        # Add age / gender to existing investigation table
        migrations.AddField(
            model_name='ultrasoundinvestigation',
            name='age',
            field=models.CharField(blank=True, max_length=10),
        ),
        migrations.AddField(
            model_name='ultrasoundinvestigation',
            name='gender',
            field=models.CharField(
                blank=True, max_length=10,
                choices=[('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other')]
            ),
        ),
        # Add age / gender to historical table
        migrations.AddField(
            model_name='historicalultrasoundinvestigation',
            name='age',
            field=models.CharField(blank=True, max_length=10),
        ),
        migrations.AddField(
            model_name='historicalultrasoundinvestigation',
            name='gender',
            field=models.CharField(
                blank=True, max_length=10,
                choices=[('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other')]
            ),
        ),
        # Create UltrasoundExpense model
        migrations.CreateModel(
            name='UltrasoundExpense',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('category', models.CharField(
                    choices=[
                        ('consumables', 'Consumables / Gel'),
                        ('maintenance', 'Machine Maintenance'),
                        ('staff', 'Staff / Salary'),
                        ('utilities', 'Utilities'),
                        ('other', 'Other'),
                    ],
                    default='other', max_length=50,
                )),
                ('description', models.CharField(max_length=300)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=12)),
                ('remarks', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'ordering': ['-date', '-created_at'],
            },
        ),
    ]
