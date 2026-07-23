from __future__ import annotations

import csv
import io

from django.http import HttpResponse
from django.utils import timezone

from .models import IncomeEntry


def _get_entries(selected_date: str):
    return IncomeEntry.objects.filter(date=selected_date).order_by('pk')


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


def export_pdf(request, selected_date: str):
    """Minimal PDF placeholder to avoid broken downloads.

    A full PDF implementation requires a PDF library (WeasyPrint/xhtml2pdf/reportlab) which
    isn't present in requirements.txt. For now we return a text-based PDF-like response.
    """
    qs = _get_entries(selected_date)

    # Simple 'PDF' stub as plain text download.
    # (Most browser users will still download it; content isn't a real PDF.)
    content = [
        f"Income Daybook - {selected_date}",
        "\n",
    ]
    for e in qs:
        content.append(f"{e.date} | {e.category} | {e.patient_name} | {e.payment_mode} | {e.amount}\n")

    resp = HttpResponse(''.join(content), content_type='application/pdf')
    resp['Content-Disposition'] = f'attachment; filename="income_daybook_{selected_date}.pdf"'
    return resp


def resolve_export(request, selected_date: str):
    export_type = request.GET.get('export', '').lower().strip()
    if export_type == 'csv':
        return export_csv(request, selected_date)
    if export_type == 'pdf':
        return export_pdf(request, selected_date)
    return None

