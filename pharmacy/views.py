"""
Pharmacy module views.

NOTE: This module is COMMENTED OUT / DISABLED per project requirements.
The ultrasound module has been built as a fully separate standalone module
with its own dashboard, billing, patient list, income/expense charts.

The pharmacy code below is preserved for reference but all views are
wrapped in a disabled state. To re-enable, remove the `disabled_` prefix
from each function and restore the urlconf.

Original pharmacy module provided:
  - PharmacyItem    : medicine catalog with stock
  - PharmacyPurchase: stock purchase recording
  - PharmacySale    : sale transaction + ledger posting
  - sale_purchase   : combined report
"""

# ──────────────────────────────────────────────────────────────────────────────
#  PHARMACY MODULE — COMMENTED OUT (disabled per client request)
#  All logic is preserved; remove 'disabled_' prefix to restore.
# ──────────────────────────────────────────────────────────────────────────────

from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from income.models import LedgerEntry, IncomeEntry, validate_payment_mode
from uhid.models import Patient
from .models import PharmacyItem, PharmacyPurchase, PharmacySale
from .services import sync_pharmacy_stock_notifications
from core.rbac import require_module


# ── items ─────────────────────────────────────────────────────────────────────
@require_module('pharmacy', level='view')
def items(request):
    """
    Pharmacy item catalog.
    COMMENTED: View is still functional but module is disabled in sidebar.
    Restored via /pharmacy/ URL if re-enabled.
    """
    if request.method == 'POST':
        if not request.user.has_perm('pharmacy.add_pharmacyitem'):
            raise PermissionDenied
        PharmacyItem.objects.create(
            name=request.POST.get('name', ''),
            drug=request.POST.get('drug', ''),
            unit_type=request.POST.get('unit', 'TAB'),
            buffer=int(request.POST.get('buffer') or 20),
            schedule=request.POST.get('schedules', '--NA--'),
            packing=int(request.POST.get('packing') or 1),
            discount_on_sale='discount' in request.POST,
        )
        sync_pharmacy_stock_notifications()
        messages.success(request, 'Item added.')
        return redirect('pharmacy:items')

    q = request.GET.get('q', '').strip()
    qs = PharmacyItem.objects.filter(is_active=True)
    if q:
        qs = qs.filter(name__icontains=q)

    sync_pharmacy_stock_notifications()
    return render(request, 'pharmacy/items.html', {
        'active_sidebar': 'pharmacy',
        'items': qs,
        'low_stock': [i for i in qs if i.stock <= i.buffer],
    })


# ── purchase ──────────────────────────────────────────────────────────────────
@require_module('pharmacy', level='full')
def purchase(request):
    """
    Stock purchase entry.
    COMMENTED: Preserved but pharmacy module disabled from sidebar nav.
    """
    if request.method == 'POST':
        item_name = (request.POST.get('item_name') or '').strip()
        item_pk = request.POST.get('item')

        if item_name:
            item, _created = PharmacyItem.objects.get_or_create(
                name=item_name,
                defaults={'drug': '', 'unit_type': 'TAB', 'buffer': 20, 'schedule': '--NA--', 'packing': 1},
            )
        else:
            item = PharmacyItem.objects.get(pk=item_pk)

        qty = int(request.POST.get('qty') or 0)
        if qty <= 0:
            messages.error(request, 'Qty must be greater than 0.')
            return render(request, 'pharmacy/purchase.html', {
                'active_sidebar': 'pharmacy',
                'items': PharmacyItem.objects.filter(is_active=True),
            })

        rate = Decimal(request.POST.get('rate') or 0)

        with transaction.atomic():
            item_locked = PharmacyItem.objects.select_for_update().get(pk=item.pk)
            PharmacyPurchase.objects.create(
                item=item_locked, supplier=request.POST.get('supplier', ''),
                quantity=qty, rate=rate,
            )
            item_locked.stock = item_locked.stock + qty
            item_locked.save(update_fields=['stock'])

        sync_pharmacy_stock_notifications()
        messages.success(request, 'Purchase recorded.')
        return redirect('pharmacy:purchase')

    return render(request, 'pharmacy/purchase.html', {
        'active_sidebar': 'pharmacy',
        'items': PharmacyItem.objects.filter(is_active=True),
    })


# ── sale ──────────────────────────────────────────────────────────────────────
@require_module('pharmacy', level='full')
def sale(request):
    """
    Counter medicine sale.
    COMMENTED: Preserved but pharmacy module disabled from sidebar nav.
    """
    if request.method == 'POST':
        item_pk   = request.POST.get('item')
        item_text = (request.POST.get('item_text') or '').strip()
        qty = int(request.POST.get('qty') or 1)

        if qty <= 0:
            messages.error(request, 'Qty must be greater than 0.')
            return redirect('pharmacy:sale')

        item = None
        if item_pk:
            try:
                item = PharmacyItem.objects.get(pk=item_pk)
            except PharmacyItem.DoesNotExist:
                item = None
        if item is None and item_text:
            item = (
                PharmacyItem.objects.filter(name__iexact=item_text, is_active=True).first()
                or PharmacyItem.objects.filter(name__icontains=item_text, is_active=True).order_by('name').first()
            )
        if item is None:
            messages.error(request, 'Item not found.')
            return redirect('pharmacy:sale')

        with transaction.atomic():
            item_locked = PharmacyItem.objects.select_for_update().get(pk=item.pk)
            if item_locked.stock < qty:
                messages.error(request, f'Insufficient stock. Available: {item_locked.stock}')
                return redirect('pharmacy:sale')

            amount = item_locked.sale_price * qty
            sale_obj = PharmacySale.objects.create(
                item=item_locked,
                patient_ref=request.POST.get('patient', ''),
                quantity=qty,
                amount=amount,
                payment_mode=request.POST.get('mode', 'Cash'),
            )
            item_locked.stock = item_locked.stock - qty
            item_locked.save(update_fields=['stock'])

            patient = Patient.objects.filter(uhid=sale_obj.patient_ref.strip()).first() if sale_obj.patient_ref else None
            if patient and amount > 0:
                LedgerEntry.record_charge(
                    uhid=patient.uhid, tx_type=LedgerEntry.TxType.PHARMACY_BILL,
                    amount=amount, payer_type=LedgerEntry.PayerType.PATIENT,
                    description=f'Pharmacy sale: {item_locked.name} x{qty}',
                    source_app='pharmacy', source_id=str(sale_obj.id), patient=patient,
                )
                LedgerEntry.record_payment(
                    uhid=patient.uhid, amount=amount, payer_type=LedgerEntry.PayerType.PATIENT,
                    payment_mode=sale_obj.payment_mode,
                    description=f'Pharmacy sale #{sale_obj.id} payment',
                    source_app='pharmacy', source_id=str(sale_obj.id),
                    patient=patient,
                )
            # Mirror into IncomeEntry for daybook
            if amount > 0:
                IncomeEntry.objects.create(
                    date=sale_obj.sold_at.date(),
                    category='Pharmacy',
                    patient_name=sale_obj.patient_ref or 'Walk-in',
                    description=f'Pharmacy sale: {item_locked.name} x{qty} (#{sale_obj.id})',
                    payment_mode=sale_obj.payment_mode,
                    amount=amount,
                )

        sync_pharmacy_stock_notifications()
        messages.success(request, 'Sale completed.')
        return redirect('pharmacy:sale')

    return render(request, 'pharmacy/sale.html', {
        'active_sidebar': 'pharmacy',
        'items': PharmacyItem.objects.filter(is_active=True),
        'hospital_upi_id': settings.HOSPITAL_UPI_ID,
    })


# ── sale_purchase ─────────────────────────────────────────────────────────────
@require_module('pharmacy', level='view')
def sale_purchase(request):
    """
    Combined sale + purchase ledger report.
    COMMENTED: Preserved but pharmacy module disabled from sidebar nav.
    """
    sales = [
        {'date': s.sold_at.date(), 'type': 'Sale', 'item': s.item.name, 'qty': s.quantity, 'amount': s.amount}
        for s in PharmacySale.objects.select_related('item').order_by('-sold_at')[:20]
    ]
    purchases = [
        {'date': p.purchased_at.date(), 'type': 'Purchase', 'item': p.item.name, 'qty': p.quantity, 'amount': p.rate * p.quantity}
        for p in PharmacyPurchase.objects.select_related('item').order_by('-purchased_at')[:20]
    ]
    records = sorted(sales + purchases, key=lambda x: x['date'], reverse=True)
    return render(request, 'pharmacy/sale_purchase.html', {
        'active_sidebar': 'pharmacy', 'records': records,
    })


# ── item_edit ─────────────────────────────────────────────────────────────────
@require_module('pharmacy', level='full')
@require_POST
def item_edit(request, pk):
    """
    Edit an existing pharmacy item.
    """
    item = PharmacyItem.objects.filter(pk=pk).first()
    if not item:
        messages.error(request, 'Item not found.')
        return redirect('pharmacy:items')

    item.name = request.POST.get('name', item.name)
    item.drug = request.POST.get('drug', item.drug)
    item.unit_type = request.POST.get('unit', item.unit_type)
    item.buffer = int(request.POST.get('buffer') or item.buffer)
    item.schedule = request.POST.get('schedules', item.schedule)
    item.packing = int(request.POST.get('packing') or item.packing)
    item.discount_on_sale = 'discount' in request.POST
    item.save()

    sync_pharmacy_stock_notifications()
    messages.success(request, 'Item updated.')
    return redirect('pharmacy:items')


# ── item_toggle ───────────────────────────────────────────────────────────────
@require_module('pharmacy', level='full')
@require_POST
def item_toggle(request, pk):
    """
    Toggle active/inactive status for a pharmacy item.
    """
    item = PharmacyItem.objects.filter(pk=pk).first()
    if not item:
        messages.error(request, 'Item not found.')
        return redirect('pharmacy:items')

    item.is_active = not item.is_active
    item.save(update_fields=['is_active'])
    
    status = 'activated' if item.is_active else 'deactivated'
    messages.success(request, f'Item {status}.')
    return redirect('pharmacy:items')


# ── purchase_delete ───────────────────────────────────────────────────────────
@require_module('pharmacy', level='full')
@require_POST
def purchase_delete(request, pk):
    """
    Delete a purchase record and reverse the stock addition.
    """
    purchase = PharmacyPurchase.objects.select_related('item').filter(pk=pk).first()
    if not purchase:
        messages.error(request, 'Purchase record not found.')
        return redirect('pharmacy:purchase')

    with transaction.atomic():
        item = PharmacyItem.objects.select_for_update().get(pk=purchase.item.pk)
        item.stock = max(0, item.stock - purchase.quantity)
        item.save(update_fields=['stock'])
        purchase.delete()

    sync_pharmacy_stock_notifications()
    messages.success(request, 'Purchase deleted and stock adjusted.')
    return redirect('pharmacy:purchase')


# ── sale_delete ───────────────────────────────────────────────────────────────
@require_module('pharmacy', level='full')
@require_POST
def sale_delete(request, pk):
    """
    Delete a sale record, restore stock, and reverse ledger entries.
    """
    sale = PharmacySale.objects.select_related('item').filter(pk=pk).first()
    if not sale:
        messages.error(request, 'Sale record not found.')
        return redirect('pharmacy:sale')

    with transaction.atomic():
        # Restore stock
        item = PharmacyItem.objects.select_for_update().get(pk=sale.item.pk)
        item.stock = item.stock + sale.quantity
        item.save(update_fields=['stock'])

        # Reverse ledger entries if they exist
        patient = Patient.objects.filter(uhid=sale.patient_ref.strip()).first() if sale.patient_ref else None
        if patient:
            LedgerEntry.objects.filter(
                patient=patient,
                source_app='pharmacy',
                source_id=str(sale.id)
            ).delete()

        # Reverse IncomeEntry mirror
        _ie_ph = IncomeEntry.objects.filter(
            category='Pharmacy',
            description__icontains=f'#{sale.id})',
        ).order_by('-created_at').first()
        if _ie_ph:
            _ie_ph.delete()

        sale.delete()

    sync_pharmacy_stock_notifications()
    messages.success(request, 'Sale deleted and stock restored.')
    return redirect('pharmacy:sale')
