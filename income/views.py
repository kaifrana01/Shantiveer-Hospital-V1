import datetime

from django.conf import settings
from django.http import HttpResponseNotAllowed
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.db.models import Sum
from django.contrib import messages

from .models import IncomeEntry, validate_payment_amount, validate_payment_mode
from core.rbac import require_module


def _parse_date(raw):
    """Safely parse an ISO date string from GET params.
    Returns a date object, or today's date if the input is invalid.
    """
    if not raw:
        return timezone.localdate()
    try:
        return datetime.date.fromisoformat(raw.strip())
    except (ValueError, AttributeError):
        return timezone.localdate()


@require_module('income', level='view')
def daybook(request):
    selected_date = _parse_date(request.GET.get('date'))

    entries = IncomeEntry.objects.filter(date=selected_date)

    def fmt(qs, mode):
        return qs.filter(payment_mode=mode).aggregate(s=Sum('amount'))['s'] or 0

    totals = {
        'cash':   f'{fmt(entries, "Cash"):,.2f}',
        'online': f'{fmt(entries, "UPI"):,.2f}',
        'card':   f'{fmt(entries, "Card"):,.2f}',
        'cheque': f'{fmt(entries, "Cheque"):,.2f}',
        'income': f'{entries.aggregate(s=Sum("amount"))["s"] or 0:,.2f}',
    }

    data = [{
        'id':          e.id,
        'date':        e.date.strftime('%d-%b-%Y'),
        'category':    e.category,
        'patient':     e.patient_name,
        'description': e.description,
        'mode':        e.payment_mode,
        'amount':      f'{e.amount:,.2f}',
        'source_app':  e.source_app,   # blank = manual; non-blank = auto-generated (OPD/IPD/Lab etc.)
    } for e in entries]

    return render(request, 'income/daybook.html', {
        'active_sidebar': 'income',
        'selected_date':  selected_date.isoformat(),
        'entries':        data,
        'totals':         totals,
        'categories':     IncomeEntry.CATEGORIES,
        'payment_modes':  IncomeEntry.PAYMENT_MODES,
    })


@require_module('income', level='full')
def income_add(request):
    """Manual income entry form for accountant / billing staff."""
    if request.method == 'POST':
        date_raw = request.POST.get('date') or timezone.localdate().isoformat()
        category = request.POST.get('category', 'OPD')
        patient_name = (request.POST.get('patient_name') or '').strip()
        description = (request.POST.get('description') or '').strip()
        payment_mode = (request.POST.get('payment_mode') or 'Cash').strip()
        amount_raw = (request.POST.get('amount') or '').strip()

        errors = []
        if not patient_name:
            errors.append('Patient / Party name is required.')
        if not description:
            errors.append('Description is required.')

        # Validate category against allowed choices
        valid_categories = [c[0] for c in IncomeEntry.CATEGORIES]
        if category not in valid_categories:
            category = 'OPD'

        # Validate payment mode
        try:
            payment_mode = validate_payment_mode(
                payment_mode, allowed=[m[0] for m in IncomeEntry.PAYMENT_MODES]
            )
        except ValueError as e:
            errors.append(str(e))

        # Validate amount
        amount = None
        try:
            amount = validate_payment_amount(amount_raw)
        except ValueError as e:
            errors.append(str(e))

        if errors:
            for err in errors:
                messages.error(request, err)
        else:
            IncomeEntry.objects.create(
                date=date_raw,
                category=category,
                patient_name=patient_name,
                description=description,
                payment_mode=payment_mode,
                amount=amount,
            )
            messages.success(request, 'Income entry saved.')
            return redirect('income:daybook')

    return render(request, 'income/income_add.html', {
        'active_sidebar': 'income_add',
        'today': timezone.localdate().isoformat(),
        'categories': IncomeEntry.CATEGORIES,
        'payment_modes': IncomeEntry.PAYMENT_MODES,
        'hospital_upi_id': settings.HOSPITAL_UPI_ID,
    })


@require_module('income', level='full')
def income_delete(request, pk):
    """Delete a manual income entry (POST only).

    BUG-13 FIX: only entries that were manually created (source_app blank)
    are deletable from the daybook UI.  Auto-generated entries posted by
    OPD/IPD/Lab/Ultrasound/Pharmacy carry a non-blank source_app and must
    be reversed through the originating module (by editing/deleting the
    visit or bill there) to keep the LedgerEntry in sync.  Deleting them
    directly here would leave orphaned ledger rows and break patient balances.
    """
    if request.method != 'POST':
        from django.http import HttpResponseNotAllowed
        return HttpResponseNotAllowed(['POST'])
    entry = get_object_or_404(IncomeEntry, pk=pk)

    if entry.source_app:
        messages.error(
            request,
            f'This entry was auto-generated by the {entry.source_app.upper()} module '
            f'and cannot be deleted here. To reverse it, delete or edit the originating '
            f'bill/visit in that module.'
        )
        return redirect('income:daybook')

    entry.delete()
    messages.success(request, 'Income entry deleted.')
    return redirect('income:daybook')
