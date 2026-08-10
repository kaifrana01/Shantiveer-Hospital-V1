"""
ShantiVeer HMS — Full Database Seeder
=====================================
Replace the contents of:
  accounts/management/commands/seed_database.py
with this file, then run:
  python manage.py seed_database

This seeds:
  • 8 doctors
  • 35 patients   (Indian names, realistic ages/addresses)
  • 35 OPD visits with prescriptions
  • 10 IPD admissions (mix of General, Private, ICU)
  • 12 lab tests master  +  20 lab investigations
  • 15 pharmacy items  +  purchases  +  sales
  • Beds, income entries, test interpretations

No user accounts are created. Run:
  python manage.py createsuperuser
to create your admin account.
"""

from decimal import Decimal
from datetime import date, time, timedelta
import random

from django.core.management.base import BaseCommand

from uhid.models import Patient
from masterdata.models import Doctor, TestInterpretation
from opd.models import OPDVisit
from prescription.models import Prescription, PrescriptionMedicine
from ipd.models import IPDAdmission, DischargeSummary, IPDPayment
from lab.models import LabTestMaster, LabInvestigation, LabInvestigationItem
from pharmacy.models import PharmacyItem, PharmacySale, PharmacyPurchase
from income.models import IncomeEntry
from core.models import Bed


# ──────────────────────────────────────────────
# Raw data tables
# ──────────────────────────────────────────────

PATIENTS_DATA = [
    # (title, name, gender, dob_year, mobile, blood_group, city, state, address, guardian, marital)
    ('Mr',  'Aarav Sharma',        'Male',   1990, '9811001001', 'B+',  'Haridwar',    'Uttarakhand', 'Shivaji Nagar, Haridwar',          'Ramesh Sharma',   'Married'),
    ('Mrs', 'Sunita Devi',         'Female', 1978, '9811001002', 'O+',  'Rishikesh',   'Uttarakhand', '12 Ganga Vihar, Rishikesh',        'Mohan Devi',      'Married'),
    ('Mr',  'Rajesh Kumar',        'Male',   1985, '9811001003', 'A+',  'Dehradun',    'Uttarakhand', '45 Rajpur Road, Dehradun',         'Suresh Kumar',    'Married'),
    ('Ms',  'Pooja Verma',         'Female', 1995, '9811001004', 'AB+', 'Roorkee',     'Uttarakhand', 'Near Clock Tower, Roorkee',        'Ramesh Verma',    'Single'),
    ('Mr',  'Mohit Agarwal',       'Male',   1982, '9811001005', 'B-',  'Muzaffarnagar','UP',          'Shastri Nagar, Muzaffarnagar',     'Sunil Agarwal',   'Married'),
    ('Mrs', 'Anita Chauhan',       'Female', 1970, '9811001006', 'O-',  'Meerut',      'UP',          '7 Civil Lines, Meerut',            'Deepak Chauhan',  'Married'),
    ('Mr',  'Vikas Yadav',         'Male',   1993, '9811001007', 'A-',  'Saharanpur',  'UP',          'Gandhi Road, Saharanpur',          'Raju Yadav',      'Single'),
    ('Mr',  'Deepak Tiwari',       'Male',   1975, '9811001008', 'AB-', 'Haridwar',    'Uttarakhand', 'Jwalapur Bypass, Haridwar',        'Kiran Tiwari',    'Married'),
    ('Mrs', 'Kavita Rawat',        'Female', 1988, '9811001009', 'B+',  'Pauri',       'Uttarakhand', 'Main Market, Pauri Garhwal',       'Bharat Rawat',    'Married'),
    ('Mr',  'Suresh Negi',         'Male',   1965, '9811001010', 'O+',  'Chamoli',     'Uttarakhand', 'Gopeshwar, Chamoli',               'Gopal Negi',      'Married'),
    ('Ms',  'Riya Singh',          'Female', 2000, '9811001011', 'A+',  'Noida',       'UP',          'Sector 18, Noida',                 'Anil Singh',      'Single'),
    ('Mr',  'Amit Joshi',          'Male',   1987, '9811001012', 'B+',  'Almora',      'Uttarakhand', 'Mall Road, Almora',                'Harish Joshi',    'Married'),
    ('Mrs', 'Meena Pant',          'Female', 1972, '9811001013', 'O+',  'Nainital',    'Uttarakhand', 'Tallital, Nainital',               'Dinesh Pant',     'Married'),
    ('Mr',  'Rohit Gupta',         'Male',   1998, '9811001014', 'AB+', 'Delhi',       'Delhi',       'Laxmi Nagar, Delhi',               'Arun Gupta',      'Single'),
    ('Mrs', 'Shobha Bisht',        'Female', 1960, '9811001015', 'B-',  'Pithoragarh', 'Uttarakhand', 'Near DC Office, Pithoragarh',      'Ram Bisht',       'Married'),
    ('Mr',  'Naveen Pandey',       'Male',   1991, '9811001016', 'O+',  'Haridwar',    'Uttarakhand', 'Ranipur More, Haridwar',           'Vijay Pandey',    'Married'),
    ('Ms',  'Priya Bhandari',      'Female', 1996, '9811001017', 'A+',  'Kotdwara',    'Uttarakhand', 'Sidcul Area, Kotdwara',            'Dinesh Bhandari', 'Single'),
    ('Mr',  'Manoj Saxena',        'Male',   1979, '9811001018', 'B+',  'Agra',        'UP',          'Taj Ganj, Agra',                   'Sanjay Saxena',   'Married'),
    ('Mrs', 'Geeta Bhatt',         'Female', 1983, '9811001019', 'O-',  'Tehri',       'Uttarakhand', 'Old Tehri Road, Tehri',            'Gopal Bhatt',     'Married'),
    ('Mr',  'Sunil Arora',         'Male',   1969, '9811001020', 'AB+', 'Ludhiana',    'Punjab',      'Model Town, Ludhiana',             'Mohan Arora',     'Married'),
    ('Ms',  'Neha Kapoor',         'Female', 1994, '9811001021', 'A-',  'Chandigarh',  'Punjab',      'Sector 22, Chandigarh',            'Ramesh Kapoor',   'Single'),
    ('Mr',  'Pankaj Chaudhary',    'Male',   1986, '9811001022', 'B+',  'Haridwar',    'Uttarakhand', 'BHEL, Haridwar',                   'Satish Chaudhary','Married'),
    ('Mrs', 'Usha Kumari',         'Female', 1958, '9811001023', 'O+',  'Rishikesh',   'Uttarakhand', 'Laxman Jhula, Rishikesh',          'Ramu Kumari',     'Married'),
    ('Mr',  'Ajay Thakur',         'Male',   1992, '9811001024', 'A+',  'Shimla',      'HP',          'Mall Road, Shimla',                'Vijay Thakur',    'Single'),
    ('Mrs', 'Rekha Nautiyal',      'Female', 1977, '9811001025', 'B+',  'Pauri',       'Uttarakhand', 'Srinagar Road, Pauri',             'Suresh Nautiyal', 'Married'),
    ('Mr',  'Kiran Dobhal',        'Male',   1984, '9811001026', 'O+',  'Haridwar',    'Uttarakhand', 'Kankhal, Haridwar',                'Satya Dobhal',    'Married'),
    ('Ms',  'Divya Malhotra',      'Female', 1999, '9811001027', 'AB-', 'Gurgaon',     'Haryana',     'DLF Phase 2, Gurgaon',             'Rakesh Malhotra', 'Single'),
    ('Mr',  'Vinod Nair',          'Male',   1973, '9811001028', 'A+',  'Kochi',       'Kerala',      'Marine Drive, Kochi',              'Suresh Nair',     'Married'),
    ('Mrs', 'Sarita Joshi',        'Female', 1981, '9811001029', 'B-',  'Dehradun',    'Uttarakhand', 'Prem Nagar, Dehradun',             'Mohan Joshi',     'Married'),
    ('Mr',  'Rakesh Dimri',        'Male',   1967, '9811001030', 'O+',  'Uttarkashi',  'Uttarakhand', 'Old Bus Stand, Uttarkashi',        'Kishan Dimri',    'Married'),
    ('Ms',  'Ankita Rawat',        'Female', 2001, '9811001031', 'A+',  'Rishikesh',   'Uttarakhand', 'Ram Jhula Area, Rishikesh',        'Bharat Rawat',    'Single'),
    ('Mr',  'Hemant Barthwal',     'Male',   1989, '9811001032', 'B+',  'Haridwar',    'Uttarakhand', 'Jwalapur, Haridwar',               'Prakash Barthwal','Married'),
    ('Mrs', 'Pushpa Lingwal',      'Female', 1963, '9811001033', 'O-',  'Chamoli',     'Uttarakhand', 'Joshimath, Chamoli',               'Ram Lingwal',     'Married'),
    ('Mr',  'Sachin Kandpal',      'Male',   1997, '9811001034', 'AB+', 'Haldwani',    'Uttarakhand', 'Shyam Nagar, Haldwani',            'Mohan Kandpal',   'Single'),
    ('Mrs', 'Lata Gosain',         'Female', 1971, '9811001035', 'B+',  'Haridwar',    'Uttarakhand', 'Motichur, Haridwar',               'Ramesh Gosain',   'Married'),
]

DOCTORS_DATA = [
    ('Dr. Neha Sharma',    'General Medicine',  'Physician',             '9876540001'),
    ('Dr. Rajesh Kumar',   'Orthopedics',       'Orthopedic Surgeon',    '9876540002'),
    ('Dr. Sunita Agarwal', 'Gynecology',        'Gynecologist',          '9876540003'),
    ('Dr. Amit Bhatt',     'Cardiology',        'Cardiologist',          '9876540004'),
    ('Dr. Pradeep Rawat',  'Pediatrics',        'Pediatrician',          '9876540005'),
    ('Dr. Kavita Joshi',   'Dermatology',       'Dermatologist',         '9876540006'),
    ('Dr. Vijay Singh',    'Surgery',           'General Surgeon',       '9876540007'),
    ('Dr. Meera Pant',     'ENT',               'ENT Specialist',        '9876540008'),
]

DIAGNOSES = [
    ('Viral Fever',           'Tab Paracetamol 500mg 1-0-1 x 5 days, Cap Azithromycin 500mg OD x 3 days'),
    ('Hypertension',          'Tab Amlodipine 5mg OD, Tab Atenolol 50mg OD'),
    ('Diabetes Mellitus',     'Tab Metformin 500mg 1-0-1, Tab Glimepiride 1mg OD morning'),
    ('Acute Gastroenteritis', 'Tab Ondansetron 4mg SOS, ORS Sachets, Tab Norflox-TZ BD x 5 days'),
    ('Upper Respiratory Tract Infection', 'Tab Amoxicillin 500mg TDS x 5 days, Syp Benadryl 10ml BD'),
    ('Migraine',              'Tab Sumatriptan 50mg SOS, Tab Propranolol 40mg BD'),
    ('Hypothyroidism',        'Tab Thyroxine 50mcg OD empty stomach'),
    ('Anaemia',               'Tab Ferrous Sulphate 200mg OD, Folic Acid 5mg OD'),
    ('Lower Back Pain',       'Tab Diclofenac 50mg BD, Tab Thiocolchicoside 4mg BD, Physiotherapy advised'),
    ('Urinary Tract Infection','Tab Norfloxacin 400mg BD x 5 days, Tab Phenazopyridine SOS'),
]

LAB_TESTS = [
    ('CBC - Complete Blood Count',            250),
    ('Blood Sugar Fasting',                   80),
    ('Blood Sugar PP',                        80),
    ('HbA1c',                                 350),
    ('Lipid Profile',                         450),
    ('LFT - Liver Function Test',             450),
    ('KFT - Kidney Function Test',            500),
    ('Thyroid Profile T3 T4 TSH',             550),
    ('Urine Routine & Microscopy',            120),
    ('ESR',                                   100),
    ('Serum Uric Acid',                       150),
    ('Serum Electrolytes',                    300),
    ('AEC - Absolute Eosinophil Count',       150),
    ('PT - INR',                              200),
    ('COVID-19 RT-PCR',                       700),
    ('Dengue NS1 Antigen',                    600),
    ('Malaria Antigen Test',                  250),
    ('Widal Test',                            150),
    ('X-Ray Chest PA View',                   300),
    ('ECG - 12 Lead',                         200),
]

PHARMACY_ITEMS = [
    # (name, drug, unit_type, schedule, packing, buffer, stock, sale_price)
    ('PARACETAMOL 500MG',    'Paracetamol',       'TAB', 'OTC',         10,  50, 500, 2.50),
    ('PARACIP 1000MG IV',    'Paracetamol IV',    'INJ', 'SCHEDULE E1',  1,  15,   8, 80.00),
    ('AZITHROMYCIN 500MG',   'Azithromycin',      'TAB', 'SCHEDULE H',   6,  20, 120, 18.00),
    ('AMOXICILLIN 500MG',    'Amoxicillin',       'CAP', 'SCHEDULE H',  10,  25, 200, 8.00),
    ('AMLODIPINE 5MG',       'Amlodipine',        'TAB', 'SCHEDULE H',  10,  30, 150, 5.50),
    ('METFORMIN 500MG',      'Metformin',         'TAB', 'SCHEDULE H',  10,  30, 300, 4.00),
    ('ONDANSETRON 4MG',      'Ondansetron',       'TAB', 'SCHEDULE H',  10,  20, 100, 12.00),
    ('DICLOFENAC 50MG',      'Diclofenac',        'TAB', 'SCHEDULE H',  10,  25, 180, 6.00),
    ('NORFLOXACIN 400MG',    'Norfloxacin',       'TAB', 'SCHEDULE H',  10,  20, 120, 10.00),
    ('ORS SACHET',           'ORS',               'SAC', 'OTC',          1,  40, 400, 15.00),
    ('SUMATRIPTAN 50MG',     'Sumatriptan',       'TAB', 'SCHEDULE H1',  4,  10,  40, 45.00),
    ('THYROXINE 50MCG',      'Levothyroxine',     'TAB', 'SCHEDULE H',  10,  25, 200, 3.50),
    ('FERROUS SULPHATE',     'Ferrous Sulphate',  'TAB', 'OTC',         10,  30, 250, 2.00),
    ('MEDICINE TEST 2',      'Test Drug',         'TAB', 'SCHEDULE A',  10,  20,   5, 25.00),
    ('RINGER LACTATE 500ML', 'Ringer Lactate',    'BOT', 'SCHEDULE C',   1,  15,  50, 65.00),
]

IPD_CASES = [
    # (patient_index, room_no, category, diagnosis, consultant, status)
    (0,  '101', 'General', 'Typhoid Fever',              'Dr. Neha Sharma',    'Admitted'),
    (2,  '205', 'Private', 'Fracture Right Femur',       'Dr. Rajesh Kumar',   'Admitted'),
    (1,  'ICU1','ICU',     'Pneumonia with Sepsis',       'Dr. Amit Bhatt',     'Admitted'),
    (5,  '102', 'General', 'Post-operative Care',         'Dr. Vijay Singh',    'Discharged'),
    (7,  '301', 'Deluxe',  'Acute MI - Stable',           'Dr. Amit Bhatt',     'Admitted'),
    (9,  'ICU2','ICU',     'Diabetic Ketoacidosis',       'Dr. Neha Sharma',    'Discharged'),
    (11, '203', 'Private', 'Appendicitis Post-op',        'Dr. Vijay Singh',    'Discharged'),
    (13, '103', 'General', 'Dengue Fever',                'Dr. Pradeep Rawat',  'Admitted'),
    (15, '302', 'Deluxe',  'Hypertensive Crisis',         'Dr. Amit Bhatt',     'Admitted'),
    (17, '104', 'General', 'Cellulitis Left Leg',         'Dr. Kavita Joshi',   'Discharged'),
]

BED_LAYOUT = [
    ('101', 'B1'), ('101', 'B2'), ('102', 'B1'), ('102', 'B2'),
    ('103', 'B1'), ('104', 'B1'), ('203', 'B1'), ('205', 'B1'),
    ('301', 'B1'), ('302', 'B1'), ('ICU1','B1'), ('ICU2','B1'),
]


# ──────────────────────────────────────────────
# Management Command
# ──────────────────────────────────────────────

class Command(BaseCommand):
    help = 'Seed HMS database with 35-patient demo data'

    def handle(self, *args, **options):
        self.stdout.write('=== ShantiVeer HMS Seeder ===')
        self.stdout.write(self.style.WARNING(
            '  Note: no user accounts are created by this command.\n'
            '  Run "python manage.py createsuperuser" to create an admin account.'
        ))

        if Patient.objects.exists():
            self.stdout.write(self.style.WARNING(
                'Patients already exist — skipping. '
                'Delete the DB file and run migrations again to re-seed.'
            ))
            return

        # ── Doctors ─────────────────────────────────
        doctors = []
        for name, dept, spec, phone in DOCTORS_DATA:
            d = Doctor.objects.create(name=name, department=dept, specialization=spec, phone=phone)
            doctors.append(d)
        self.stdout.write(f'✓ {len(doctors)} doctors created')

        # ── Patients ────────────────────────────────
        patients = []
        base_year = 2026
        for i, (title, name, gender, birth_year, mobile, bg, city, state, addr, guardian, marital) in enumerate(PATIENTS_DATA):
            age = base_year - birth_year
            p = Patient.objects.create(
                uhid=str(3490 + i),
                title=title,
                name=name,
                gender=gender,
                dob=date(birth_year, random.randint(1, 12), random.randint(1, 28)),
                age_years=age,
                mobile=mobile,
                blood_group=bg,
                city=city,
                state=state,
                address=addr,
                guardian=guardian,
                guardian_relation='S/o' if gender == 'Male' else 'D/o',
                marital_status=marital,
                resident='India',
            )
            patients.append(p)
        self.stdout.write(f'✓ {len(patients)} patients created')

        # ── Lab Test Master ──────────────────────────
        lab_masters = []
        for name, rate in LAB_TESTS:
            t = LabTestMaster.objects.create(name=name, rate=Decimal(str(rate)))
            lab_masters.append(t)
        self.stdout.write(f'✓ {len(lab_masters)} lab test types created')

        # ── Pharmacy Items + Purchases ───────────────
        pharm_items = []
        for name, drug, unit, sched, packing, buffer, stock, price in PHARMACY_ITEMS:
            item = PharmacyItem.objects.create(
                name=name, drug=drug, unit_type=unit, schedule=sched,
                packing=packing, buffer=buffer, stock=stock,
                sale_price=Decimal(str(price)),
            )
            pharm_items.append(item)
            PharmacyPurchase.objects.create(
                item=item, supplier='Medico Distributors Pvt Ltd',
                quantity=stock + 50, rate=Decimal(str(round(price * 0.6, 2))),
            )
        self.stdout.write(f'✓ {len(pharm_items)} pharmacy items created')

        # ── OPD Visits + Prescriptions ───────────────
        opd_count = 0
        visit_dates = [
            date(2026, 4, 10), date(2026, 4, 15), date(2026, 4, 22),
            date(2026, 5, 1),  date(2026, 5, 8),  date(2026, 5, 14),
            date(2026, 5, 20), date(2026, 5, 28), date(2026, 6, 3),
            date(2026, 6, 8),  date(2026, 6, 10), date(2026, 6, 12),
            date(2026, 6, 14), date(2026, 6, 16), date(2026, 6, 18),
            date(2026, 6, 19), date(2026, 6, 20), date(2026, 6, 21),
            date(2026, 6, 22), date(2026, 6, 23), date(2026, 6, 23),
            date(2026, 6, 23), date(2026, 6, 24), date(2026, 6, 24),
            date(2026, 6, 24), date(2026, 6, 24), date(2026, 6, 24),
            date(2026, 6, 24), date(2026, 6, 24), date(2026, 6, 24),
            date(2026, 6, 24), date(2026, 6, 24), date(2026, 6, 24),
            date(2026, 6, 24), date(2026, 6, 24),
        ]
        visit_times = [
            time(9, 0), time(9, 30), time(10, 0), time(10, 30), time(11, 0),
            time(11, 30), time(12, 0), time(14, 0), time(14, 30), time(15, 0),
        ]
        fees_options = [300, 400, 500, 600]
        payment_modes = ['Cash', 'UPI', 'Cash', 'Cash', 'Card']

        for idx, patient in enumerate(patients):
            diag_idx = idx % len(DIAGNOSES)
            diagnosis, medicines = DIAGNOSES[diag_idx]
            doc = doctors[idx % len(doctors)]
            vt = visit_times[idx % len(visit_times)]
            fees = Decimal(fees_options[idx % len(fees_options)])
            pmode = payment_modes[idx % len(payment_modes)]

            visit = OPDVisit.objects.create(
                patient=patient,
                date=visit_dates[idx],
                time=vt,
                doctor_name=doc.name,
                fees=fees,
                discount=Decimal('0'),
                total_amount=fees,
                payment_mode=pmode,
                head='OPD Consultation',
                referral='Self' if idx % 3 != 0 else 'PHC Referral',
            )

            pres = Prescription.objects.create(
                opd_visit=visit,
                diagnosis=diagnosis,
                medicines=medicines,
                advice='Rest for 3 days. Light diet. Follow up after 5 days.',
            )

            # Link 1–2 pharmacy items to prescription
            for pm_idx in range(min(2, len(pharm_items))):
                item = pharm_items[(idx + pm_idx) % len(pharm_items)]
                PrescriptionMedicine.objects.create(
                    prescription=pres,
                    medicine_name=item.name,
                    dosage='1-0-1 x 5 days',
                    quantity=5,
                    pharmacy_item=item,
                    status='pending',
                )

            # Income entry for each OPD
            IncomeEntry.objects.create(
                date=visit_dates[idx],
                category='OPD',
                patient_name=f'{patient.title}. {patient.name}',
                description=f'OPD Consultation – {doc.name}',
                payment_mode=pmode,
                amount=fees,
            )
            opd_count += 1

        self.stdout.write(f'✓ {opd_count} OPD visits + prescriptions created')

        # ── IPD Admissions ───────────────────────────
        ipd_count = 0
        admit_dates = [
            date(2026, 6, 1), date(2026, 6, 3), date(2026, 6, 5),
            date(2026, 6, 8), date(2026, 6, 10), date(2026, 6, 12),
            date(2026, 6, 14), date(2026, 6, 16), date(2026, 6, 18), date(2026, 6, 20),
        ]
        for i, (pat_idx, room, cat, diag, consultant, status) in enumerate(IPD_CASES):
            patient = patients[pat_idx]
            admit_date = admit_dates[i]
            adm = IPDAdmission.objects.create(
                patient=patient,
                date=admit_date,
                time=time(10 + i % 8, 0),
                guardian=patient.guardian,
                category=cat,
                consultant=consultant,
                room_no=room,
                diagnosis=diag,
                status=status,
                kyc_type='Aadhar',
                kyc_no=f'1234-5678-{9000 + i}',
            )
            # Advance payment
            IPDPayment.objects.create(
                admission=adm,
                amount=Decimal('5000'),
                payment_mode='Cash',
                remarks='Advance on admission',
            )
            # Discharge if status is Discharged
            if status == 'Discharged':
                DischargeSummary.objects.create(
                    admission=adm,
                    discharge_date=admit_date + timedelta(days=4),
                    notes=f'Patient recovered well. Advised follow-up in OPD after 1 week. Diagnosis: {diag}.',
                )
            ipd_count += 1

        self.stdout.write(f'✓ {ipd_count} IPD admissions created')

        # ── Lab Investigations ──────────────────────
        lab_count = 0
        test_groups = [
            [0, 1, 2],      # CBC + Sugar tests
            [5, 6],         # LFT + KFT
            [3, 7],         # HbA1c + Thyroid
            [4, 9],         # Lipid + ESR
            [15, 16, 17],   # Dengue + Malaria + Widal
            [18, 19],       # X-Ray + ECG
            [8, 13],        # Urine + PT-INR
        ]
        lab_dates = [
            date(2026, 6, 1), date(2026, 6, 5), date(2026, 6, 8),
            date(2026, 6, 10), date(2026, 6, 12), date(2026, 6, 15),
            date(2026, 6, 18), date(2026, 6, 20), date(2026, 6, 22),
            date(2026, 6, 23), date(2026, 6, 24), date(2026, 6, 24),
            date(2026, 6, 24), date(2026, 6, 24), date(2026, 6, 24),
            date(2026, 6, 24), date(2026, 6, 24), date(2026, 6, 24),
            date(2026, 6, 24), date(2026, 6, 24),
        ]
        for idx in range(20):
            patient = patients[idx % len(patients)]
            group_idx = idx % len(test_groups)
            test_indices = test_groups[group_idx]
            tests_for_inv = [lab_masters[ti] for ti in test_indices if ti < len(lab_masters)]
            total = sum(t.rate for t in tests_for_inv)
            pmode = ['Cash', 'UPI', 'Cash'][idx % 3]

            inv = LabInvestigation.objects.create(
                patient=patient,
                patient_name=f'{patient.title}. {patient.name}',
                mobile=patient.mobile,
                test_date=lab_dates[idx],
                total=total,
                payment_mode=pmode,
                consultant=doctors[idx % len(doctors)].name,
                referred_by=doctors[(idx + 2) % len(doctors)].name,
                address=patient.address,
            )
            for t in tests_for_inv:
                LabInvestigationItem.objects.create(
                    investigation=inv, test=t, rate=t.rate, quantity=1, amount=t.rate
                )
            IncomeEntry.objects.create(
                date=lab_dates[idx],
                category='Investigation',
                patient_name=f'{patient.title}. {patient.name}',
                description=', '.join(t.name for t in tests_for_inv),
                payment_mode=pmode,
                amount=total,
            )
            lab_count += 1

        self.stdout.write(f'✓ {lab_count} lab investigations created')

        # ── Pharmacy Sales ───────────────────────────
        for idx, patient in enumerate(patients[:20]):
            item = pharm_items[idx % len(pharm_items)]
            qty = random.randint(1, 5)
            amount = Decimal(str(qty)) * item.sale_price
            PharmacySale.objects.create(
                item=item,
                patient_ref=patient.uhid,
                quantity=qty,
                amount=amount,
                payment_mode=['Cash', 'UPI'][idx % 2],
            )

        self.stdout.write('✓ 20 pharmacy sales created')

        # ── Beds ─────────────────────────────────────
        admitted_patients = [patients[pi] for pi, *_ in IPD_CASES if _[-1] == 'Admitted']
        ipd_rooms = [(r, cat) for (_, r, cat, *__) in IPD_CASES if __[-1] == 'Admitted']

        for i, (room, bed) in enumerate(BED_LAYOUT):
            occupied = i < len(admitted_patients)
            Bed.objects.create(
                room_no=room,
                bed_no=bed,
                status='Occupied' if occupied else 'Vacant',
                patient=admitted_patients[i] if occupied else None,
            )

        self.stdout.write(f'✓ {len(BED_LAYOUT)} beds created')

        # ── Test Interpretations ─────────────────────
        interp_data = [
            ('CBC - Complete Blood Count',
             'Normal RBC: 4.5–5.5 M/μL (Male), 4.0–5.0 (Female). WBC: 4,000–11,000/μL. Platelet: 1.5–4.5 L/μL.'),
            ('Blood Sugar Fasting',
             'Normal: <100 mg/dL. Pre-diabetes: 100–125. Diabetes: ≥126 mg/dL on two separate tests.'),
            ('HbA1c',
             'Normal: <5.7%. Pre-diabetes: 5.7–6.4%. Diabetes: ≥6.5%. Each 1% ≈ 28.7 mg/dL avg glucose.'),
            ('Lipid Profile',
             'Total Cholesterol <200 mg/dL. LDL <100 mg/dL. HDL >40 (Male), >50 (Female). TG <150 mg/dL.'),
            ('Thyroid Profile T3 T4 TSH',
             'TSH: 0.4–4.0 mIU/L. T3: 80–200 ng/dL. T4: 5.1–14.1 μg/dL. High TSH = Hypothyroid. Low TSH = Hyperthyroid.'),
            ('KFT - Kidney Function Test',
             'Creatinine: 0.7–1.2 mg/dL (Male), 0.5–1.0 (Female). BUN: 7–25 mg/dL. eGFR >60 = normal.'),
            ('NT-PRO-BETA NATRIURETIC PEPTIDE (NT-PRO-BNP)',
             'NT-Pro BNP values increase with age. Values <125 pg/mL: CHF unlikely. >900 pg/mL: High probability of CHF.'),
        ]
        for tn, interp in interp_data:
            TestInterpretation.objects.get_or_create(
                test_name=tn,
                defaults={'interpretation': interp, 'status': 'Active'},
            )

        self.stdout.write('✓ Test interpretations created')

        # ── Summary ──────────────────────────────────
        self.stdout.write(self.style.SUCCESS(
            '\n'
            '════════════════════════════════════════\n'
            '  DATABASE SEEDED SUCCESSFULLY!\n'
            '════════════════════════════════════════\n'
            '  Login URL : http://127.0.0.1:8000/\n'
            '  Run "python manage.py createsuperuser"\n'
            '  to create your admin account.\n'
            '════════════════════════════════════════'
        ))