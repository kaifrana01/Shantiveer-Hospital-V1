from collections import defaultdict
import datetime
from decimal import Decimal

from django.contrib import messages
from django.db.models import Sum
from django.shortcuts import redirect, render, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import AdvanceExpensesForm, BasicExpensesForm
from .models import Expense
from core.rbac import require_module


def _parse_date(raw):
    """Safely parse an ISO date string. Returns None if invalid."""
    if not raw:
        return None
    try:
        return datetime.date.fromisoformat(raw.strip())
    except (ValueError, AttributeError):
        return None


@require_module('expenses', level='full')
def expenses_page(request):
    today = timezone.localdate()
    selected_date = request.GET.get('date')
    if selected_date:
        parsed = _parse_date(selected_date)
        if parsed:
            today = parsed

    filter_category = request.GET.get('category')

    base_qs = Expense.objects.all()
    if filter_category:
        base_qs = base_qs.filter(category=filter_category)

    # tables + charts
    chart_total = base_qs.aggregate(s=Sum('amount'))['s'] or 0

    # category-wise (for pie chart)
    breakdown = (
        base_qs.values('expense_type', 'category')
        .annotate(total=Sum('amount'))
        .order_by('-total')
    )

    # date-wise/day-wise etc tables (separate basic + advance)
    basic_qs = Expense.objects.filter(expense_type=Expense.ExpenseType.BASIC)
    advance_qs = Expense.objects.filter(expense_type=Expense.ExpenseType.ADVANCE)

    def _make_expense_rows(qs):
        # most recent 100 rows for table
        return [
            {
                'date': str(r.date),
                'category': r.category,
                'amount': r.amount,
                'remarks': r.remarks,
                'paid_to': r.paid_to,
                'id': r.id,
            }
            for r in qs.order_by('-date', '-created_at')[:100]
        ]

    def _pivot_rows(qs, category_choices):
        """Group expense rows created together (same submission / batch_id)
        into a single register row with one Amount+Name pair per category:
        Date | Remarks | Cut (amt/name) | Pharmacy (amt/name) | ...
        Legacy rows saved before batch_id existed fall back to one row each.
        """
        groups = {}
        order = []
        for r in qs.order_by('-date', '-created_at')[:300]:
            key = r.batch_id or f'legacy-{r.id}'
            if key not in groups:
                groups[key] = {
                    'date': r.date,
                    'remarks': r.remarks,
                    'amounts': {c: Decimal('0') for c, _ in category_choices},
                    'names': {c: [] for c, _ in category_choices},
                    'total': Decimal('0'),
                    'ids': [],
                }
                order.append(key)
            g = groups[key]
            g['amounts'][r.category] = g['amounts'].get(r.category, Decimal('0')) + r.amount
            if r.paid_to:
                g['names'][r.category].append(r.paid_to)
            g['total'] += r.amount
            g['ids'].append(r.id)
            # keep earliest/latest date+remarks consistent for the group
            if r.date > g['date']:
                g['date'] = r.date

        rows = []
        for key in order:
            g = groups[key]
            g['names'] = {c: ', '.join(v) for c, v in g['names'].items()}
            rows.append(g)
        rows.sort(key=lambda x: x['date'], reverse=True)

        column_totals = {c: Decimal('0') for c, _ in category_choices}
        grand_total = Decimal('0')
        for row in rows:
            for c, _ in category_choices:
                column_totals[c] += row['amounts'].get(c, Decimal('0'))
            grand_total += row['total']

        return rows, column_totals, grand_total

    basic_rows = _make_expense_rows(basic_qs)
    advance_rows = _make_expense_rows(advance_qs)

    # aggregated day/week/month/year totals for dashboard section within expenses page
    def _aggregate(qs, mode):
        from django.db.models.functions import TruncDay, TruncMonth
        from datetime import timedelta
        today = timezone.localdate()
        if mode == 'day':
            # last 7 days
            date_from = today - timedelta(days=6)
            labels = [(today - timedelta(days=6 - i)).strftime('%d %b') for i in range(7)]
            trunc = TruncDay('date')
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
        if mode == 'week':
            # same as day aggregation but labels Mon..Sun for last 7 days
            date_from = today - timedelta(days=6)
            labels = [(today - timedelta(days=6 - i)).strftime('%a') for i in range(7)]
            trunc = TruncDay('date')
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
        if mode == 'month':
            date_from = today - timedelta(days=29)
            labels = [(today - timedelta(days=29 - i)).strftime('%d') for i in range(30)]
            trunc = TruncDay('date')
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
        # year
        labels = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
        from django.db.models.functions import TruncMonth
        rows = (
            qs.filter(date__year=today.year)
            .annotate(m=TruncMonth('date'))
            .values('m')
            .annotate(s=Sum('amount'))
            .order_by('m')
        )
        m = {r['m'].month: float(r['s'] or 0) for r in rows if r.get('m')}
        values = [m.get(i+1, 0.0) for i in range(12)]
        return labels, values

    basic_day_labels, basic_day_values = _aggregate(basic_qs, 'day')
    basic_week_labels, basic_week_values = _aggregate(basic_qs, 'week')
    basic_month_labels, basic_month_values = _aggregate(basic_qs, 'month')
    basic_year_labels, basic_year_values = _aggregate(basic_qs, 'year')

    advance_day_labels, advance_day_values = _aggregate(advance_qs, 'day')
    advance_week_labels, advance_week_values = _aggregate(advance_qs, 'week')
    advance_month_labels, advance_month_values = _aggregate(advance_qs, 'month')
    advance_year_labels, advance_year_values = _aggregate(advance_qs, 'year')


    if request.method == 'POST':
        if request.POST.get('form') == 'basic':
            form = BasicExpensesForm(request.POST)
            advance_form = AdvanceExpensesForm(initial={'date': request.POST.get('date') or today})
            if form.is_valid():
                created = form.create_rows(user=request.user)
                if created:
                    messages.success(request, 'Basic expenses saved.')
                else:
                    messages.warning(request, 'Duplicate submission detected — entry already saved.')
                return redirect('expenses:page')
        else:
            form = BasicExpensesForm(initial={'date': today})
            advance_form = AdvanceExpensesForm(request.POST)
            if advance_form.is_valid():
                created = advance_form.create_rows(user=request.user)
                if created:
                    messages.success(request, 'Advance expenses saved.')
                else:
                    messages.warning(request, 'Duplicate submission detected — entry already saved.')
                return redirect('expenses:page')

    else:
        form = BasicExpensesForm(initial={'date': today})
        advance_form = AdvanceExpensesForm(initial={'date': today})

    categories = []
    for r in breakdown:
        categories.append({
            'expense_type': r['expense_type'],
            'category': r['category'],
            'total': r['total'] or 0,
        })

    # Apply optional date filter for date-wise table + chart
    date_from = _parse_date(request.GET.get('date_from'))
    date_to = _parse_date(request.GET.get('date_to'))

    def _apply_date_range(qs):
        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)
        return qs

    basic_rows_final = _make_expense_rows(_apply_date_range(basic_qs))
    advance_rows_final = _make_expense_rows(_apply_date_range(advance_qs))

    basic_pivot_rows, basic_pivot_totals, basic_pivot_grand_total = _pivot_rows(
        _apply_date_range(basic_qs), Expense.BasicCategory.choices
    )
    advance_pivot_rows, advance_pivot_totals, advance_pivot_grand_total = _pivot_rows(
        _apply_date_range(advance_qs), Expense.AdvanceCategory.choices
    )

    # Recompute chart totals for the selected range (basic + advance separately)
    def _re_aggregate(qs, mode):
        return _aggregate(qs, mode)

    basic_day_labels2, basic_day_values2 = _re_aggregate(_apply_date_range(basic_qs), 'day')
    basic_week_labels2, basic_week_values2 = _re_aggregate(_apply_date_range(basic_qs), 'week')
    basic_month_labels2, basic_month_values2 = _re_aggregate(_apply_date_range(basic_qs), 'month')
    basic_year_labels2, basic_year_values2 = _re_aggregate(_apply_date_range(basic_qs), 'year')

    advance_day_labels2, advance_day_values2 = _re_aggregate(_apply_date_range(advance_qs), 'day')
    advance_week_labels2, advance_week_values2 = _re_aggregate(_apply_date_range(advance_qs), 'week')
    advance_month_labels2, advance_month_values2 = _re_aggregate(_apply_date_range(advance_qs), 'month')
    advance_year_labels2, advance_year_values2 = _re_aggregate(_apply_date_range(advance_qs), 'year')

    return render(request, 'expenses/expenses.html', {
        'active_sidebar': 'expenses',
        'basic_form': form,
        'advance_form': advance_form,
        'breakdown': categories,
        'chart_total': chart_total,
        'filter_category': filter_category,
        'basic_rows': basic_rows_final,
        'advance_rows': advance_rows_final,
        'basic_pivot_rows': basic_pivot_rows,
        'basic_pivot_totals': basic_pivot_totals,
        'basic_pivot_grand_total': basic_pivot_grand_total,
        'basic_categories': Expense.BasicCategory.choices,
        'advance_pivot_rows': advance_pivot_rows,
        'advance_pivot_totals': advance_pivot_totals,
        'advance_pivot_grand_total': advance_pivot_grand_total,
        'advance_categories': Expense.AdvanceCategory.choices,
        'basic_day_labels': basic_day_labels2,
        'basic_day_values': basic_day_values2,
        'basic_week_labels': basic_week_labels2,
        'basic_week_values': basic_week_values2,
        'basic_month_labels': basic_month_labels2,
        'basic_month_values': basic_month_values2,
        'basic_year_labels': basic_year_labels2,
        'basic_year_values': basic_year_values2,
        'advance_day_labels': advance_day_labels2,
        'advance_day_values': advance_day_values2,
        'advance_week_labels': advance_week_labels2,
        'advance_week_values': advance_week_values2,
        'advance_month_labels': advance_month_labels2,
        'advance_month_values': advance_month_values2,
        'advance_year_labels': advance_year_labels2,
        'advance_year_values': advance_year_values2,
        'date_from': date_from.isoformat() if date_from else '',
        'date_to': date_to.isoformat() if date_to else '',
    })




@require_module('expenses', level='full')
@require_POST
def expense_delete(request, pk):
    """Delete a single expense row by primary key (POST only)."""
    expense = get_object_or_404(Expense, pk=pk)
    expense.delete()
    messages.success(request, 'Expense entry deleted.')
    return redirect('expenses:page')
