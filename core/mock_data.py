"""Demo data matching screenshot UI — replace with DB queries later."""

from datetime import date


def opd_records():
    return [
        {'id': 1, 'opd_no': 'OPD028', 'uhid': '3491', 'name': 'Naveen Jain', 'gender': 'Male', 'phone': '9811256863', 'date': '2026-05-01', 'total': '500.00', 'diagnosis': '', 'medicines': '', 'advice': ''},
        {'id': 2, 'opd_no': 'OPD027', 'uhid': '3490', 'name': 'AMIR ALAM', 'gender': 'Male', 'phone': '9012409842', 'date': '2026-06-08', 'total': '300.00', 'diagnosis': 'Fever', 'medicines': 'Tab Paracetamol 500mg', 'advice': 'Rest'},
        {'id': 3, 'opd_no': 'OPD026', 'uhid': '3489', 'name': 'VIVEK TYAGI', 'gender': 'Male', 'phone': '9876543210', 'date': '2026-06-07', 'total': '500.00', 'diagnosis': '', 'medicines': '', 'advice': ''},
    ]


def ipd_patients():
    return [
        {'id': 1, 'name': 'Naveen Jain', 'age': 25, 'gender': 'FEMALE', 'uhid': '3491', 'ipd_no': 'IPD101', 'consultant': 'Dr. Neha Sharma', 'room': '101', 'diagnosis': 'Typhoid', 'date': '2026-06-01', 'status': 'Admitted', 'category': 'General'},
        {'id': 2, 'name': 'VIVEK TYAGI', 'age': 32, 'gender': 'MALE', 'uhid': '3489', 'ipd_no': 'IPD102', 'consultant': 'Dr. Rajesh Kumar', 'room': '205', 'diagnosis': 'Fracture', 'date': '2026-06-05', 'status': 'Admitted', 'category': 'PRIVATE'},
        {'id': 3, 'name': 'AMIR ALAM', 'age': 21, 'gender': 'MALE', 'uhid': '3493', 'ipd_no': 'IPD103', 'consultant': 'Dr. Neha Sharma', 'room': 'ICU01', 'diagnosis': 'Pneumonia', 'date': '2026-06-08', 'status': 'Admitted', 'category': 'ICU'},
    ]


def present_patients():
    return [dict(p, room=p['room'], ipd_no=p['ipd_no'], category=p['category']) for p in ipd_patients()]


def uhid_patients():
    return [
        {'uhid': '3493', 'name': 'AMIR ALAM', 'gender': 'Male', 'age': '21', 'mobile': '9012409842'},
        {'uhid': '3492', 'name': 'Priya Singh', 'gender': 'Female', 'age': '28', 'mobile': '9988776655'},
        {'uhid': '3491', 'name': 'Naveen Jain', 'gender': 'Male', 'age': '35', 'mobile': '9811256863'},
        {'uhid': '3490', 'name': 'Rahul Verma', 'gender': 'Male', 'age': '42', 'mobile': '9123456789'},
    ]


def lab_tests():
    return [
        {'name': 'ESR', 'rate': 100}, {'name': 'AEC', 'rate': 150}, {'name': 'ANC', 'rate': 200},
        {'name': 'APTT', 'rate': 350}, {'name': 'ADA', 'rate': 400}, {'name': 'AST', 'rate': 120},
        {'name': 'CBC', 'rate': 250}, {'name': 'KFT', 'rate': 500}, {'name': 'LFT', 'rate': 450},
    ]


def lab_reports():
    return [
        {'id': 1, 'bill_no': 'LAB001', 'patient': 'Mr. AMIR ALAM', 'tests': 'KFT, CBC', 'amount': '1000', 'date': '2026-06-09'},
        {'id': 2, 'bill_no': 'LAB002', 'patient': 'Mr. Naveen Jain', 'tests': 'ESR, AEC', 'amount': '250', 'date': '2026-06-08'},
    ]


def pharmacy_items():
    return [
        {'name': 'MEDICINE TEST 2', 'schedule': 'SCHEDULE A', 'unit': 'TAB', 'hsn': '3006 (9% + 9%)', 'packing': 10, 'buffer': 20},
        {'name': 'PARACIP 1000MG IV', 'schedule': 'SCHEDULE E1', 'unit': 'INJ', 'hsn': '3004 (6% + 6%)', 'packing': 1, 'buffer': 15},
        {'name': 'CROSIN TAB', 'schedule': '--NA--', 'unit': 'TAB', 'hsn': '3004 (6% + 6%)', 'packing': 10, 'buffer': 25},
    ]


def dashboard_stats():
    return {
        'appointment_key': 146,
        'appointment_past': 0,
        'total_billing': '1,200.00',
        'collections': '1,700.00',
        'rev_billing': '0.00',
        'avg_contact': '0.00',
    }


def dashboard_beds():
    return [
        {'room': '101', 'bed_no': 'B1', 'status': 'Occupied', 'occupied': True, 'patient': 'Naveen Jain'},
        {'room': '102', 'bed_no': 'B2', 'status': 'Vacant', 'occupied': False, 'patient': ''},
        {'room': 'ICU01', 'bed_no': 'B1', 'status': 'Occupied', 'occupied': True, 'patient': 'AMIR ALAM'},
        {'room': '205', 'bed_no': 'B1', 'status': 'Occupied', 'occupied': True, 'patient': 'VIVEK TYAGI'},
    ]


def today_appointments():
    return [
        {'name': 'AMIR ALAM', 'gender': 'Male', 'date': '2026-06-09'},
        {'name': 'Priya Singh', 'gender': 'Female', 'date': '2026-06-09'},
        {'name': 'Rahul Verma', 'gender': 'Male', 'date': '2026-06-09'},
    ]


def emergency_patients():
    return [
        {'name': 'Emergency Case 1', 'date': '2026-06-09'},
        {'name': 'Emergency Case 2', 'date': '2026-06-09'},
    ]


def discharge_list():
    return [
        {'id': 1, 'ipd_no': 'IPD099', 'name': 'Suresh Kumar', 'age': 45, 'gender': 'Male', 'guardian': 'Ram Kumar', 'room': '110', 'contact': '9876543210', 'consultant': 'Dr. Neha Sharma', 'discharge_date': '2026-06-08'},
    ]


def daybook_entries():
    return [
        {'date': '09-Jun-2026', 'category': 'Investigation', 'patient': 'Mr. AMIR ALAM', 'description': 'DIAGNOSTIC UNIT - KIDNEY FUNCTION TEST (KFT), COMPLETE BLOOD COUNT (CBC)', 'mode': 'Cash', 'amount': '1,000.00'},
        {'date': '09-Jun-2026', 'category': 'Investigation', 'patient': 'Mr. Naveen Jain', 'description': 'ESR, AEC', 'mode': 'Cash', 'amount': '80.00'},
    ]


def daybook_totals():
    return {'cash': '1,080.00', 'online': '0.00', 'card': '0.00', 'cheque': '0.00', 'income': '1,080.00'}


def interpretations():
    return [
        {'test_name': 'NT-PRO-BETA NATRIURETIC PEPTIDE (NT-PRO-BNP)', 'text': 'NT-Pro BNP values increase with age. <50 Years: high sensitivity. 50-75 Years: moderate risk. >75 years: elevated levels indicate CHF.', 'status': 'Active'},
    ]


def doctors():
    return [
        {'name': 'Dr. Neha Sharma', 'department': 'General Medicine', 'specialization': 'Physician', 'phone': '9876543210'},
        {'name': 'Dr. Rajesh Kumar', 'department': 'Orthopedics', 'specialization': 'Orthopedic', 'phone': '9876543211'},
    ]
