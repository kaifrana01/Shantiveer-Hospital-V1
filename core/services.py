"""Database queries for dashboard and APIs."""
import logging
from datetime import timedelta
from django.db.models import Sum, Count, Q
from django.utils import timezone
from django.db.models import Sum, F, DecimalField, ExpressionWrapper

logger = logging.getLogger('hms.dashboard')

# Whitelist of supported chart ranges. Any view that takes a `range`
# query param should validate against this set instead of trusting the
# raw string straight into business logic / cache keys.
VALID_RANGES = {'today', 'week', 'month', 'year'}

# Room categories shown as their own series on the income chart. Any
# IPD admission category that doesn't match one of these (typos, blank,
# custom wards, etc.) is bucketed into "Other" so the chart total always
# reconciles with the real room-charge collections.
ROOM_CATEGORY_BUCKETS = ['ICU', 'Private', 'General']


def _range_to_date_from(range_filter, today):
    """Resolve a validated range_filter into a start date. Raises
    ValueError for anything not in VALID_RANGES so callers fail loudly
    instead of silently aggregating the wrong window."""
    if range_filter not in VALID_RANGES:
        raise ValueError(f'Unsupported range_filter: {range_filter!r}')
    if range_filter == 'today':
        return today
    if range_filter == 'week':
        return today - timedelta(days=6)
    if range_filter == 'year':
        return today.replace(month=1, day=1)
    return today - timedelta(days=29)  # month


def get_income_breakdown(range_filter='month'):
    """Income chart data for the dashboard, split the way the billing
    desk actually thinks about money:

      - Doctor Fees        -> OPD consultation fees collected (OPDVisit)
      - Medicine Charges    -> Pharmacy counter sales + medicines billed
                                directly against an IPD admission
      - Room Charges (ICU/Private/General/Other) -> IPD payments,
                                bucketed by the admission's room category
      - Investigations       -> Lab / Ultrasound charges already posted
                                to IncomeEntry
      - Other Income         -> anything in IncomeEntry that doesn't
                                belong to the buckets above (so the
                                total always reconciles — nothing is
                                silently dropped from the chart)

    Every sub-query is isolated in its own try/except: if one module's
    tables aren't migrated yet or a query fails, that slice degrades to
    zero instead of taking down the whole dashboard.
    """
    today = timezone.localdate()
    try:
        date_from = _range_to_date_from(range_filter, today)
    except ValueError:
        logger.warning('Invalid dashboard range_filter received, defaulting to month')
        range_filter = 'month'
        date_from = _range_to_date_from(range_filter, today)

    def _safe_sum(label, fn):
        try:
            return float(fn() or 0)
        except Exception:
            logger.exception('Dashboard income breakdown: failed computing %s', label)
            return 0.0

    # --- Doctor Fees: OPD consultation collections ----------------------
    def _doctor_fees():
        from opd.models import OPDVisit
        return OPDVisit.objects.filter(date__gte=date_from).aggregate(
            s=Sum('total_amount'))['s']

    doctor_fees = _safe_sum('doctor_fees', _doctor_fees)

    # --- Medicine Charges: pharmacy sales + IPD medicine lines ----------
    def _medicine_charges():
        from pharmacy.models import PharmacySale
        total = PharmacySale.objects.filter(
            sold_at__date__gte=date_from).aggregate(s=Sum('amount'))['s'] or 0
        try:
            from ipd.models import IPDMedicineLine
            total += IPDMedicineLine.objects.filter(
                admission__date__gte=date_from).aggregate(s=Sum('amount'))['s'] or 0
        except Exception:
            logger.exception('Dashboard income breakdown: IPD medicine lines unavailable')
        return total

    medicine_charges = _safe_sum('medicine_charges', _medicine_charges)

    # --- Room Charges: IPD payments bucketed by room category -----------
    room_charges = {bucket: 0.0 for bucket in ROOM_CATEGORY_BUCKETS}
    room_charges['Other'] = 0.0

    def _room_charges():
        from ipd.models import IPDPayment
        rows = (
            IPDPayment.objects
            .filter(admission__date__gte=date_from)
            .values('admission__category')
            .annotate(s=Sum('amount'))
        )
        for row in rows:
            category = (row['admission__category'] or '').strip()
            amount = float(row['s'] or 0)
            matched = next(
                (b for b in ROOM_CATEGORY_BUCKETS if b.lower() == category.lower()),
                None,
            )
            room_charges[matched or 'Other'] += amount
        return None

    try:
        _room_charges()
    except Exception:
        logger.exception('Dashboard income breakdown: failed computing room_charges')

    # --- Investigations: Lab + Ultrasound, already posted to IncomeEntry --
    def _investigation_charges():
        from income.models import IncomeEntry
        return IncomeEntry.objects.filter(
            date__gte=date_from, category='Investigation').aggregate(s=Sum('amount'))['s']

    investigation_charges = _safe_sum('investigation_charges', _investigation_charges)

    # --- Other Income: IncomeEntry rows not already represented above ----
    def _other_income():
        from income.models import IncomeEntry
        return IncomeEntry.objects.filter(
            date__gte=date_from
        ).exclude(category='Investigation').aggregate(s=Sum('amount'))['s']

    other_income = _safe_sum('other_income', _other_income)

    room_total = sum(room_charges.values())
    grand_total = doctor_fees + medicine_charges + room_total + investigation_charges + other_income

    return {
        'range': range_filter,
        'labels': [
            'Doctor Fees', 'Medicine Charges',
            'Room Charges (Emergency ward)', 'Room Charges (Private Ward)',
            'Room Charges (General Ward)', 'Room Charges (Other)',
            'Investigations', 'Other Income',
        ],
        'values': [
            round(doctor_fees, 2), round(medicine_charges, 2),
            round(room_charges['ICU'], 2), round(room_charges['Private'], 2),
            round(room_charges['General'], 2), round(room_charges['Other'], 2),
            round(investigation_charges, 2), round(other_income, 2),
        ],
        'doctor_fees': round(doctor_fees, 2),
        'medicine_charges': round(medicine_charges, 2),
        'room_charges': {k: round(v, 2) for k, v in room_charges.items()},
        'room_charges_total': round(room_total, 2),
        'investigation_charges': round(investigation_charges, 2),
        'other_income': round(other_income, 2),
        'total': round(grand_total, 2),
    }


def get_dashboard_expenses_timeseries(expense_type=None, range_filter='month'):
    """Return (labels, values) for expenses chart based on selected range.

    range_filter: today|week|month|year
    expense_type: None|ExpenseType value (basic|advance)
    """
    from expenses.models import Expense

    today = timezone.localdate()
    qs = Expense.objects.all()
    if expense_type:
        qs = qs.filter(expense_type=expense_type)

    if range_filter == 'today':
        # Show hourly buckets (12 hours back is overkill; keep it 24 hours but label only 6 points?)
        # Since requirement is day wise, keep it simple: last 1 day -> 1 label.
        date_from = today
        rows = (qs.filter(date=date_from).values('date').annotate(s=Sum('amount')))
        labels = [today.strftime('%d %b')]
        values = [float(list(rows)[0]['s']) if rows else 0.0]
        return labels, values

    from django.db.models.functions import TruncDay, TruncMonth

    if range_filter == 'week':
        date_from = today - timedelta(days=6)
        trunc = TruncDay('date')
        labels = [(today - timedelta(days=6 - i)).strftime('%a') for i in range(7)]
        rows = (
            qs.filter(date__gte=date_from)
            .annotate(d=trunc)
            .values('d')
            .annotate(s=Sum('amount'))
            .order_by('d')
        )
        m = {r['d']: float(r['s'] or 0) for r in rows}
        values = [m.get(today - timedelta(days=6 - i), 0.0) for i in range(7)]
        return labels, values

    if range_filter == 'year':
        date_from = today.replace(month=1, day=1)
        trunc = TruncMonth('date')
        labels = [
            ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][i]
            for i in range(12)
        ]
        rows = (
            qs.filter(date__gte=date_from)
            .annotate(d=trunc)
            .values('d')
            .annotate(s=Sum('amount'))
            .order_by('d')
        )
        m = {r['d'].month: float(r['s'] or 0) for r in rows}
        values = [m.get(i+1, 0.0) for i in range(12)]
        return labels, values

    # month (last 30 days)
    date_from = today - timedelta(days=29)
    trunc = TruncDay('date')
    labels = [(today - timedelta(days=29 - i)).strftime('%d') for i in range(30)]
    rows = (
        qs.filter(date__gte=date_from)
        .annotate(d=trunc)
        .values('d')
        .annotate(s=Sum('amount'))
        .order_by('d')
    )
    m = {r['d']: float(r['s'] or 0) for r in rows}
    values = [m.get(today - timedelta(days=29 - i), 0.0) for i in range(30)]
    return labels, values


def get_dashboard_stats():
    from opd.models import OPDVisit
    from income.models import IncomeEntry
    from uhid.models import Patient
    from ipd.models import IPDAdmission
    from core.models import Bed
    
    # Import Expense lazily so dashboard won't crash if DB migrations
    # for the new module are not yet applied.
    try:
        from expenses.models import Expense
    except Exception:
        Expense = None


    today = timezone.localdate()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)

    opd_today = OPDVisit.objects.filter(date=today).count()

    opd_week = OPDVisit.objects.filter(date__gte=week_ago).count()
    opd_month = OPDVisit.objects.filter(date__gte=month_ago).count()
    total_patients = Patient.objects.count()
    ipd_admitted = IPDAdmission.objects.filter(status='Admitted').count()

    # Billing stats
    total = IncomeEntry.objects.aggregate(s=Sum('amount'))['s'] or 0
    paid = IncomeEntry.objects.filter(payment_mode='Cash').aggregate(s=Sum('amount'))['s'] or 0
    today_income = IncomeEntry.objects.filter(date=today).aggregate(s=Sum('amount'))['s'] or 0

    # Average contact = total income / total visits (avoid division by zero)
    total_visits = OPDVisit.objects.count()
    avg_contact = (total / total_visits) if total_visits > 0 else 0

    # Bed stats
    total_beds = Bed.objects.count()
    occupied_beds = Bed.objects.filter(status='Occupied').count()

    total_expenses = 0
    if Expense is not None:
        total_expenses = Expense.objects.aggregate(s=Sum('amount'))['s'] or 0


    return {
        'appointment_key': opd_today,
        'total_expenses': f'{total_expenses:,.2f}',
        'appointment_past': OPDVisit.objects.filter(date__lt=today).count(),
        'total_billing': f'{total:,.2f}',
        'collections': f'{paid:,.2f}',
        'today_income': f'{today_income:,.2f}',
        'rev_billing': f'{(total - paid):,.2f}',
        'avg_contact': f'{avg_contact:,.2f}',
        'appointments_month': opd_month,
        'appointments_week': opd_week,
        'total_patients': total_patients,
        'ipd_admitted': ipd_admitted,
        'total_beds': total_beds,
        'occupied_beds': occupied_beds,
        'vacant_beds': total_beds - occupied_beds,
    }


def get_dashboard_beds():
    from core.models import Bed
    return [
        {
            'room': b.room_no,
            'bed_no': b.bed_no,
            'status': b.status,
            'occupied': b.occupied,
            'patient': b.patient_name,
        }
        for b in Bed.objects.select_related('patient').all()[:8]
    ]


def get_today_appointments():
    from opd.models import OPDVisit
    today = timezone.localdate()
    return [
        {
            'name': v.patient.name,
            'gender': v.patient.gender,
            'date': str(v.date),
            'doctor': v.doctor_name or '—',
            'opd_no': v.opd_no,
        }
        for v in OPDVisit.objects.filter(date=today).select_related('patient')[:10]
    ]


def get_emergency_patients():
    from ipd.models import IPDAdmission
    return [
        {'name': a.patient.name, 'date': str(a.date), 'category': a.category, 'ipd_no': a.ipd_no}
        for a in IPDAdmission.objects.filter(category='ICU', status='Admitted').select_related('patient')[:5]
    ]


def get_low_stock_medicines():
    from pharmacy.models import PharmacyItem
    from pharmacy.services import is_low_stock

    return [
        {
            'id': i.id,
            'name': i.name,
            'stock': i.stock,
            'buffer': i.buffer,
            'unit': i.unit_type,
            'urgency': 'critical' if i.stock == 0 else 'low',
        }
        for i in PharmacyItem.objects.filter(is_active=True)
        if is_low_stock(i)
    ]


def get_required_prescription_medicines():
    from prescription.models import PrescriptionMedicine

    lines = PrescriptionMedicine.objects.filter(
        status__in=[PrescriptionMedicine.STATUS_PENDING, PrescriptionMedicine.STATUS_LOW_STOCK],
    ).select_related('prescription__opd_visit__patient')[:15]

    return [
        {
            'id': line.id,
            'patient_name': line.prescription.patient.name,
            'uhid': line.prescription.patient.uhid,
            'opd_no': line.prescription.opd_visit.opd_no,
            'medicine': line.medicine_name,
            'quantity': line.quantity,
            'dosage': line.dosage,
            'status': line.get_status_display(),
            'visit_id': line.prescription.opd_visit_id,
            'stock': line.pharmacy_item.stock if line.pharmacy_item else None,
        }
        for line in lines
    ]


def get_recent_prescriptions():
    from prescription.models import Prescription

    return [
        {
            'id': p.opd_visit_id,
            'patient_name': p.patient.name,
            'uhid': p.patient.uhid,
            'opd_no': p.opd_visit.opd_no,
            'diagnosis': (p.diagnosis or '—')[:50],
            'updated': p.updated_at.strftime('%d-%m-%Y %H:%M'),
        }
        for p in Prescription.objects.select_related('opd_visit__patient').order_by('-updated_at')[:8]
    ]


def get_unread_notifications(user=None, limit=10):
    """Notification UI disabled.

    This app previously returned unread Notification model rows for dashboard/UI.
    It now intentionally returns nothing to "comment/disable notification related code"
    while keeping the backend model/routes intact.
    """
    return []


def get_unread_notification_count(user=None):
    """Notification UI disabled."""
    return 0



def patient_to_dict(p):
    return {
        'uhid': p.uhid,
        'name': p.name,
        'gender': p.gender,
        'age': p.age_display,
        'mobile': p.mobile,
    }


def _opd_due(visit):
    """Compute outstanding OPD due for a specific visit. Returns formatted string."""
    try:
        from income.models import LedgerEntry
        # OPD posts charge + payment simultaneously, so due is normally zero.
        # If there's any manual adjustment/reversal, the balance could be non-zero.
        balance = LedgerEntry.balance_for(
            uhid=visit.patient.uhid,
            payer_type=LedgerEntry.PayerType.PATIENT
        )
        return f'{balance:.2f}' if balance != 0 else '0.00'
    except Exception:
        return '--'


def opd_to_dict(v):
    from prescription.models import Prescription
    pres = Prescription.objects.filter(opd_visit=v).first()
    # Prescription amount (sum of dispensed medicine costs) + OPD visit total
    # If any line has amount/price fields in pharmacy, this can be extended.
    medicines_total = 0
    if pres:
        # Add medicine amount into OPD total for prescription list page.
        # We try to use a per-unit price field on PharmacyItem if present.
        qs = pres.medicine_lines.select_related('pharmacy_item')
        if qs.exists() and qs.first() and qs.first().pharmacy_item:
            pharmacy_item_model = qs.first().pharmacy_item.__class__
            rate_field_candidates = ['rate', 'price', 'sale_price', 'mrp', 'cost']
            rate_field = None
            for f in rate_field_candidates:
                if hasattr(pharmacy_item_model, f):
                    rate_field = f
                    break

            if rate_field:
                # PharmacyItem has commonly used price field(s): sale_price, rate, cost.
                # We only support `sale_price` here to avoid SQL/field-name issues.
                # If later you add more fields, extend this safely.
                if rate_field != 'sale_price':
                    # Fallback: use sale_price if available
                    rate_field = 'sale_price' if hasattr(pharmacy_item_model, 'sale_price') else None

            if rate_field:
                medicines_total = qs.aggregate(
                    s=Sum(f'pharmacy_item__{rate_field}')
                )['s'] or 0
                # Use a plain double-underscore path in Sum() to avoid malformed
                # expression strings getting generated into the ORM.
                # Compute extended amount: pharmacy_item.<rate_field> * quantity
                # Using ExpressionWrapper+F avoids Django treating the expression as a field name.
                if rate_field:
                    medicines_total = qs.aggregate(
                        s=Sum(
                            ExpressionWrapper(
                                F(f'pharmacy_item__{rate_field}') * F('quantity'),
                                output_field=DecimalField(),
                            )
                        )
                    )['s'] or 0


    total_value = (v.total_amount or 0) + medicines_total
    return {
        'id': v.id,
        'opd_no': v.opd_no,
        'uhid': v.patient.uhid,
        'name': v.patient.name,
        'gender': v.patient.gender,
        'phone': v.patient.mobile,
        'date': str(v.date),
        'total': f'{total_value:.2f}',
        'doctor': getattr(v, 'doctor_name', '') or '—',
        'diagnosis': pres.diagnosis if pres else '',
        'medicines': pres.medicines if pres else '',
        'advice': pres.advice if pres else '',
        # For OPD visits, we post charge + payment simultaneously at registration,
        # so due is normally zero. Use ledger balance to catch any real outstanding.
        'due': _opd_due(v),
    }

