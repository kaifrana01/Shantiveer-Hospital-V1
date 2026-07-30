from __future__ import annotations

import csv
import io
from decimal import Decimal

from django.conf import settings
from django.db.models import Sum
from django.http import HttpResponse
from django.utils import timezone
from django.contrib.auth.decorators import login_required

from .models import IncomeEntry


def _get_entries(selected_date: str):
    return IncomeEntry.objects.filter(date=selected_date).order_by('pk')


@login_required
def export_csv(request, selected_date: str):
    qs = _get_entries(selected_date)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['#', 'Date', 'Category', 'Patient Name', 'Description', 'Payment Mode', 'Amount'])

    for i, e in enumerate(qs, start=1):
        writer.writerow([i, e.date, e.category, e.patient_name, e.description, e.payment_mode, str(e.amount)])

    resp = HttpResponse(output.getvalue(), content_type='text/csv; charset=utf-8')
    resp['Content-Disposition'] = f'attachment; filename="income_daybook_{selected_date}.csv"'
    return resp


def _fmt(value) -> str:
    """Format a Decimal/None as a comma-separated currency string."""
    if value is None:
        return '0.00'
    return f'{value:,.2f}'


@login_required
def export_pdf(request, selected_date: str):
    """Generate a real PDF for the Income Daybook using xhtml2pdf."""
    from xhtml2pdf import pisa

    qs = _get_entries(selected_date)

    def mode_total(mode):
        return qs.filter(payment_mode=mode).aggregate(s=Sum('amount'))['s'] or Decimal('0')

    totals = {
        'cash':   mode_total('Cash'),
        'online': mode_total('UPI'),
        'card':   mode_total('Card'),
        'cheque': mode_total('Cheque'),
        'income': qs.aggregate(s=Sum('amount'))['s'] or Decimal('0'),
    }

    hospital_name = getattr(settings, 'HOSPITAL_NAME', 'Hospital')

    rows_html = ''
    for i, e in enumerate(qs, start=1):
        rows_html += f"""
        <tr>
            <td>{i}</td>
            <td>{e.date.strftime('%d-%b-%Y')}</td>
            <td>{e.category}</td>
            <td>{e.patient_name}</td>
            <td>{e.description}</td>
            <td>{e.payment_mode}</td>
            <td class="amount">&#8377; {_fmt(e.amount)}</td>
        </tr>"""

    if not rows_html:
        rows_html = '<tr><td colspan="7" style="text-align:center;color:#888;">No entries for this date.</td></tr>'

    html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: Arial, sans-serif; font-size: 11px; color: #222; margin: 20px; }}
  h2   {{ text-align: center; font-size: 15px; margin-bottom: 2px; }}
  .sub {{ text-align: center; font-size: 11px; color: #555; margin-bottom: 12px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}
  th   {{ background-color: #1a3c6e; color: #fff; padding: 6px 8px; text-align: left; font-size: 11px; }}
  td   {{ padding: 5px 8px; border-bottom: 1px solid #ddd; font-size: 11px; }}
  tr:nth-child(even) td {{ background-color: #f5f7fa; }}
  .amount  {{ text-align: right; }}
  .totals  {{ margin-top: 12px; width: 100%; }}
  .totals td {{ padding: 3px 8px; font-size: 11px; }}
  .totals .label {{ text-align: right; font-weight: bold; width: 85%; }}
  .totals .val   {{ text-align: right; width: 15%; }}
  .grand {{ background-color: #d4edda; font-weight: bold; }}
</style>
</head>
<body>
  <h2>{hospital_name}</h2>
  <p class="sub">Daily Lab Income – Day Book &nbsp;|&nbsp; Date: {selected_date}</p>

  <table>
    <thead>
      <tr>
        <th>#</th><th>Date</th><th>Category</th><th>Patient Name</th>
        <th>Description</th><th>Payment Mode</th><th>Amount (&#8377;)</th>
      </tr>
    </thead>
    <tbody>
      {rows_html}
    </tbody>
  </table>

  <table class="totals">
    <tr><td class="label">Total Cash</td><td class="val">&#8377; {_fmt(totals['cash'])}</td></tr>
    <tr><td class="label">Total Online (UPI)</td><td class="val">&#8377; {_fmt(totals['online'])}</td></tr>
    <tr><td class="label">Total Card Swipe</td><td class="val">&#8377; {_fmt(totals['card'])}</td></tr>
    <tr><td class="label">Total Cheque</td><td class="val">&#8377; {_fmt(totals['cheque'])}</td></tr>
    <tr class="grand"><td class="label">Total Income</td><td class="val">&#8377; {_fmt(totals['income'])}</td></tr>
  </table>
</body>
</html>"""

    pdf_buffer = io.BytesIO()
    result = pisa.CreatePDF(io.StringIO(html), dest=pdf_buffer)

    if result.err:
        return HttpResponse('Error generating PDF. Please try again.', status=500)

    pdf_buffer.seek(0)
    resp = HttpResponse(pdf_buffer.read(), content_type='application/pdf')
    resp['Content-Disposition'] = f'inline; filename="income_daybook_{selected_date}.pdf"'
    return resp


@login_required
def resolve_export(request, selected_date: str):
    export_type = request.GET.get('export', '').lower().strip()
    if export_type == 'csv':
        return export_csv(request, selected_date)
    if export_type == 'pdf':
        return export_pdf(request, selected_date)
    # Fallback: redirect to daybook instead of returning None (which causes a 500)
    from django.shortcuts import redirect
    return redirect('income:daybook')

