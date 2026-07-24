from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from simple_history.models import HistoricalRecords

# ---------------------------------------------------------------------------
# Shared payment-layer constants — single source of truth for all modules
# ---------------------------------------------------------------------------

PAYMENT_MODES_ALL = ['Cash', 'UPI', 'Card', 'Cheque', 'NEFT/RTGS']
AMOUNT_MAX = Decimal('9999999.99')   # ₹99.99 lakh — hard ceiling per transaction


def validate_payment_amount(amount, label='Amount'):
    """Raise ValueError with a user-friendly message if amount is invalid.
    Returns the cleaned Decimal.  Call this in every payment view.
    """
    try:
        amt = Decimal(str(amount).replace(',', '').strip())
    except (InvalidOperation, Exception):
        raise ValueError(f'{label}: enter a valid number.')
    if amt <= 0:
        raise ValueError(f'{label} must be greater than zero.')
    if amt > AMOUNT_MAX:
        raise ValueError(f'{label} cannot exceed ₹{AMOUNT_MAX:,.2f} per transaction.')
    return amt


def validate_payment_mode(mode, allowed=None):
    """Return the mode if it is in the allowed list, else raise ValueError."""
    allowed = allowed or PAYMENT_MODES_ALL
    if mode not in allowed:
        raise ValueError(f'Invalid payment mode: {mode!r}.')
    return mode


class IncomeEntry(models.Model):
    CATEGORIES = [
        ('Investigation', 'Investigation'),
        ('OPD', 'OPD'),
        ('IPD', 'IPD'),
        ('Pharmacy', 'Pharmacy'),
        ('Ultrasound', 'Ultrasound'),
        ('OT', 'OT'),
        ('Extra', 'Extra / Miscellaneous'),
    ]
    PAYMENT_MODES = [('Cash', 'Cash'), ('UPI', 'UPI'), ('Card', 'Card'), ('Cheque', 'Cheque')]

    date = models.DateField()
    category = models.CharField(max_length=50, choices=CATEGORIES)
    patient_name = models.CharField(max_length=200)
    description = models.TextField()
    payment_mode = models.CharField(max_length=20, choices=PAYMENT_MODES, default='Cash')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    history = HistoricalRecords()

    class Meta:
        ordering = ['-date']


class LedgerEntry(models.Model):
    """
    Phase 2/3: single source-of-truth ledger for every financial movement
    tied to a patient's UHID — charges, payments, insurance claims, TPA
    settlements, discounts and write-offs.

    Design notes:
    - Every row is one side of a transaction (a debit OR a credit), never
      both. A bill becomes a DEBIT row; money received (from the patient
      or the insurer) becomes a CREDIT row. Outstanding balance for any
      slice of the ledger is simply sum(debit) - sum(credit).
    - `payer_type` carries the split-liability: the same UHID can have a
      DEBIT owed by INSURANCE and a separate DEBIT owed by the PATIENT for
      the same admission/visit, decided at billing time (co-pay, non-
      reimbursable items, sub-limits, etc).
    - `tx_type` identifies which module produced the row, `source_app` +
      `source_id` point back at the actual billing record (OPDVisit,
      IPDAdmission, LabInvestigation, PharmacySale, ...) so the ledger
      never has to duplicate billing logic — it only mirrors money.
    - TPA settlement is just two more rows on the same UHID: a CREDIT for
      what the insurer actually paid, and a DEBIT (or WRITE_OFF/DISCOUNT
      tx_type) re-tagged to PATIENT or written off for whatever the
      insurer rejected. Reconciliation = ledger balance hits zero.
    """

    class TxType(models.TextChoices):
        OPD_BILL = 'OPD_BILL', 'OPD Consultation Charge'
        IPD_BILL = 'IPD_BILL', 'IPD Charge'
        LAB_BILL = 'LAB_BILL', 'Lab Investigation Charge'
        PHARMACY_BILL = 'PHARMACY_BILL', 'Pharmacy Sale'
        PATIENT_PAYMENT = 'PATIENT_PAYMENT', 'Payment Received from Patient'
        INSURANCE_CLAIM = 'INSURANCE_CLAIM', 'Insurance Claim Raised'
        INSURANCE_PAYMENT = 'INSURANCE_PAYMENT', 'Payment Received from Insurer (TPA)'
        INSURANCE_DISCOUNT = 'INSURANCE_DISCOUNT', 'Insurance Rejection Written Off'
        PATIENT_LIABILITY_SHIFT = 'PATIENT_LIABILITY_SHIFT', 'Rejected Amount Shifted to Patient'
        REFUND = 'REFUND', 'Refund Issued'
        ADJUSTMENT = 'ADJUSTMENT', 'Manual Adjustment'

    class PayerType(models.TextChoices):
        PATIENT = 'PATIENT', 'Patient'
        INSURANCE = 'INSURANCE', 'Insurance / TPA'

    class ClaimStatus(models.TextChoices):
        NOT_APPLICABLE = 'NA', 'Not Applicable'
        PENDING = 'PENDING', 'Claim Pending'
        PARTIALLY_SETTLED = 'PARTIAL', 'Partially Settled'
        SETTLED = 'SETTLED', 'Fully Settled'
        REJECTED = 'REJECTED', 'Rejected'

    SOURCE_APP_CHOICES = [
        ('opd', 'OPD'),
        ('ipd', 'IPD'),
        ('lab', 'Lab'),
        ('pharmacy', 'Pharmacy'),
        ('manual', 'Manual / Accounts Desk'),
    ]

    # --- Identity -----------------------------------------------------
    uhid = models.CharField(
        max_length=20, db_index=True,
        help_text="Patient UHID this entry belongs to. Kept as a plain "
                  "field (not just a FK) so the ledger survives even if "
                  "a patient record is archived or merged."
    )
    patient = models.ForeignKey(
        'uhid.Patient', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ledger_entries',
    )
    ipd_admission = models.ForeignKey(
        'ipd.IPDAdmission', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ledger_entries',
        help_text="Set when this entry is tied to a specific IPD stay "
                  "(most insurance claims originate here).",
    )

    # --- What kind of money movement this row represents ---------------
    tx_type = models.CharField(max_length=30, choices=TxType.choices)
    payer_type = models.CharField(
        max_length=20, choices=PayerType.choices, default=PayerType.PATIENT,
        help_text="Who is liable for / who paid this specific row. This "
                  "is what makes split-liability (co-pay vs claim) work: "
                  "two rows under the same UHID can carry different "
                  "payer_type values.",
    )

    # --- The actual money: exactly one of these is non-zero per row ----
    debit_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        help_text="Amount charged / owed (increases the outstanding balance).",
    )
    credit_amount = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        help_text="Amount received / waived (decreases the outstanding balance).",
    )

    description = models.CharField(max_length=300, blank=True)

    # --- Traceability back to the module that generated this row -------
    source_app = models.CharField(max_length=20, choices=SOURCE_APP_CHOICES, default='manual')
    source_id = models.CharField(
        max_length=50, blank=True,
        help_text="Primary key / bill number of the originating record "
                  "(e.g. IPD admission id, OPD visit no, Lab bill no).",
    )

    # --- Insurance / TPA specific fields --------------------------------
    tpa_name = models.CharField(max_length=200, blank=True)
    insurance_company = models.CharField(max_length=200, blank=True)
    policy_no = models.CharField(max_length=100, blank=True)
    claim_no = models.CharField(max_length=100, blank=True, db_index=True)
    claim_status = models.CharField(
        max_length=10, choices=ClaimStatus.choices, default=ClaimStatus.NOT_APPLICABLE,
    )

    payment_mode = models.CharField(
        max_length=20,
        choices=[('Cash', 'Cash'), ('UPI', 'UPI'), ('Card', 'Card'),
                  ('Cheque', 'Cheque'), ('NEFT/RTGS', 'NEFT/RTGS'), ('NA', 'NA')],
        default='NA',
    )

    remarks = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ledger_entries_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # Every ledger row is a financial/legal record (insurance claims,
    # TPA settlements, write-offs). HistoricalRecords gives a tamper-
    # evident trail of every edit, with the user attached automatically
    # via HistoryRequestMiddleware.
    history = HistoricalRecords()

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['uhid', 'payer_type']),
            models.Index(fields=['claim_no']),
            models.Index(fields=['claim_status']),
        ]
        verbose_name = 'Ledger Entry'
        verbose_name_plural = 'Ledger Entries'

    def clean(self):
        # Enforce "one side per row": a row is a debit OR a credit, not both,
        # and not neither — otherwise reconciliation queries silently lie.
        debit = self.debit_amount or Decimal('0.00')
        credit = self.credit_amount or Decimal('0.00')

        if debit > 0 and credit > 0:
            raise ValidationError(
                'A ledger entry must be either a debit or a credit, not both. '
                'Split a combined transaction into two rows instead.'
            )
        if debit == 0 and credit == 0:
            raise ValidationError('A ledger entry must have a non-zero debit or credit amount.')

        # Guard against absurdly large amounts that indicate data-entry errors
        ceiling = Decimal('99999999.99')
        if debit > ceiling or credit > ceiling:
            raise ValidationError(
                f'Amount exceeds maximum allowed value of ₹{ceiling:,.2f}.'
            )

    def save(self, *args, **kwargs):
        # Enforce clean() even when called via objects.create() or programmatic
        # helpers, not just via Django forms.
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        side = f"DR {self.debit_amount}" if self.debit_amount else f"CR {self.credit_amount}"
        return f"[{self.uhid}] {self.tx_type} ({self.payer_type}) {side}"

    # ------------------------------------------------------------------
    # Convenience query helpers — these are what the billing desk and
    # the TPA settlement screen actually call.
    # ------------------------------------------------------------------

    @classmethod
    def balance_for(cls, uhid, payer_type=None, ipd_admission_id=None):
        """Outstanding balance (debit - credit) for a UHID, optionally
        narrowed to one payer_type (PATIENT / INSURANCE) and/or one
        admission. This is the single query that replaces hunting
        through OPD/IPD/Lab/Pharmacy tables separately."""
        qs = cls.objects.filter(uhid=uhid)
        if payer_type:
            qs = qs.filter(payer_type=payer_type)
        if ipd_admission_id:
            qs = qs.filter(ipd_admission_id=ipd_admission_id)
        agg = qs.aggregate(
            total_debit=models.Sum('debit_amount'),
            total_credit=models.Sum('credit_amount'),
        )
        debit = agg['total_debit'] or Decimal('0.00')
        credit = agg['total_credit'] or Decimal('0.00')
        return debit - credit

    @classmethod
    def patient_due(cls, uhid, ipd_admission_id=None):
        """What the patient owes right now (e.g. at discharge desk)."""
        return cls.balance_for(uhid, payer_type=cls.PayerType.PATIENT,
                                ipd_admission_id=ipd_admission_id)

    @classmethod
    def insurance_due(cls, uhid, ipd_admission_id=None):
        """What is still pending from the TPA/insurer for this UHID."""
        return cls.balance_for(uhid, payer_type=cls.PayerType.INSURANCE,
                                ipd_admission_id=ipd_admission_id)

    @classmethod
    def record_charge(cls, *, uhid, tx_type, amount, payer_type,
                       description='', source_app='manual', source_id='',
                       patient=None, ipd_admission=None, **extra):
        """Post a charge (debit) row. `extra` accepts any of the
        insurance fields (tpa_name, insurance_company, policy_no,
        claim_no, claim_status) for INSURANCE-payer rows."""
        return cls.objects.create(
            uhid=uhid, patient=patient, ipd_admission=ipd_admission,
            tx_type=tx_type, payer_type=payer_type,
            debit_amount=Decimal(amount), description=description,
            source_app=source_app, source_id=str(source_id), **extra,
        )

    @classmethod
    def record_payment(cls, *, uhid, amount, payer_type, payment_mode='Cash',
                        description='', patient=None, ipd_admission=None,
                        source_app='manual', source_id='', **extra):
        """Post a payment (credit) row — from the patient at the desk or
        from the insurer via TPA settlement.

        source_app / source_id are accepted so the caller can stamp
        traceability (e.g. source_app='ipd', source_id=str(payment.id)).
        Defaults to 'manual' for backwards compatibility.
        """
        tx_type = (cls.TxType.INSURANCE_PAYMENT if payer_type == cls.PayerType.INSURANCE
                   else cls.TxType.PATIENT_PAYMENT)
        return cls.objects.create(
            uhid=uhid, patient=patient, ipd_admission=ipd_admission,
            tx_type=tx_type, payer_type=payer_type,
            credit_amount=Decimal(amount), payment_mode=payment_mode,
            description=description,
            source_app=source_app, source_id=str(source_id), **extra,
        )

    @classmethod
    def settle_insurance_claim(cls, *, uhid, claim_no, paid_amount, rejected_amount,
                                ipd_admission=None, patient=None,
                                rejection_action='SHIFT_TO_PATIENT',
                                remarks=''):
        """
        Core TPA settlement workflow described in Phase 3: given what the
        insurer actually paid vs. rejected for a claim, post the two
        balancing rows that bring the insurance balance to zero.

        rejection_action:
          - 'SHIFT_TO_PATIENT': rejected amount becomes a new PATIENT debit
             (e.g. co-pay / sub-limit breach the patient must now pay).
          - 'WRITE_OFF': rejected amount is written off by the hospital
             (e.g. goodwill discount, billing error) and never collected.
        """
        paid_amount = Decimal(paid_amount)
        rejected_amount = Decimal(rejected_amount)
        entries = []

        if paid_amount:
            entry = cls(
                uhid=uhid, patient=patient, ipd_admission=ipd_admission,
                tx_type=cls.TxType.INSURANCE_PAYMENT, payer_type=cls.PayerType.INSURANCE,
                credit_amount=paid_amount, claim_no=claim_no,
                claim_status=cls.ClaimStatus.PARTIALLY_SETTLED if rejected_amount else cls.ClaimStatus.SETTLED,
                description=f'TPA settlement payment for claim {claim_no}',
                remarks=remarks, source_app='manual',
            )
            entry.save()
            entries.append(entry)

        if rejected_amount:
            # First, close out the insurance side of the rejected slice...
            disc_entry = cls(
                uhid=uhid, patient=patient, ipd_admission=ipd_admission,
                tx_type=cls.TxType.INSURANCE_DISCOUNT, payer_type=cls.PayerType.INSURANCE,
                credit_amount=rejected_amount, claim_no=claim_no,
                claim_status=cls.ClaimStatus.PARTIALLY_SETTLED,
                description=f'Rejected portion of claim {claim_no} removed from insurance balance',
                remarks=remarks, source_app='manual',
            )
            disc_entry.save()
            entries.append(disc_entry)
            # ...then decide where that liability goes.
            if rejection_action == 'SHIFT_TO_PATIENT':
                shift_entry = cls(
                    uhid=uhid, patient=patient, ipd_admission=ipd_admission,
                    tx_type=cls.TxType.PATIENT_LIABILITY_SHIFT, payer_type=cls.PayerType.PATIENT,
                    debit_amount=rejected_amount, claim_no=claim_no,
                    description=f'Rejected by insurer on claim {claim_no} — now payable by patient',
                    remarks=remarks, source_app='manual',
                )
                shift_entry.save()
                entries.append(shift_entry)
            # WRITE_OFF: no extra row needed (hospital absorbs the shortfall)

        return entries
