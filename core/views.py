from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from core import services
from pharmacy.services import sync_pharmacy_stock_notifications
from .models import Notification, Bed
from itertools import groupby
from core.rbac import require_module


@login_required
def home(request):
    """Redirect home to the full dashboard."""
    return redirect('core:dashboard')


@login_required
def dashboard(request):
    from core.rbac import get_user_role, has_access

    sync_pharmacy_stock_notifications()
    try:
        stats = services.get_dashboard_stats()
    except Exception:
        # If migrations for newly added modules are not applied yet,
        # avoid breaking the whole dashboard.
        stats = services.get_dashboard_stats_fallback() if hasattr(services, 'get_dashboard_stats_fallback') else {}

    role = get_user_role(request.user)

    context = {
        'active_sidebar': 'dashboard',
        'stats': stats,
        'role': role,
        # Notifications disabled (server & UI polling/logic).
        'notifications': [],
    }

    # Each widget is only computed/shown if the user's role can see the
    # underlying module — keeps the dashboard relevant per role and avoids
    # leaking data (e.g. low-stock medicine alerts) to roles with no
    # access to that module at all.
    if has_access(request.user, 'beds'):
        context['beds'] = services.get_dashboard_beds()
    if has_access(request.user, 'opd_list') or has_access(request.user, 'opd_registration'):
        context['today_appointments'] = services.get_today_appointments()
    if has_access(request.user, 'ipd_list'):
        context['emergency_patients'] = services.get_emergency_patients()
    if has_access(request.user, 'pharmacy'):
        context['low_stock_medicines'] = services.get_low_stock_medicines()
    if has_access(request.user, 'prescription'):
        context['required_medicines'] = services.get_required_prescription_medicines()
        context['recent_prescriptions'] = services.get_recent_prescriptions()

    return render(request, 'core/dashboard.html', context)



@login_required
def notifications_list(request):
    sync_pharmacy_stock_notifications()
    items = Notification.objects.filter(Q(user=request.user) | Q(user__isnull=True))[:50]
    return render(request, 'core/notifications.html', {
        'active_sidebar': 'dashboard',
        'notifications': items,
    })


@login_required
def mark_notification_read(request, pk):
    notif = get_object_or_404(Notification, pk=pk)
    notif.is_read = True
    notif.save()
    if notif.link:
        return redirect(notif.link)
    return redirect('core:notifications')


@login_required
def mark_all_notifications_read(request):
    Notification.objects.filter(
        Q(user=request.user) | Q(user__isnull=True), is_read=False,
    ).update(is_read=True)
    messages.success(request, 'All notifications marked as read.')
    return redirect('core:notifications')


# ───────────────────────────────────────────
# BED MANAGEMENT VIEWS
# ───────────────────────────────────────────

@require_module('beds', level='view')
def bed_manage(request):
    """Display all beds grouped by room."""
    all_beds = Bed.objects.select_related('patient').order_by('room_no', 'bed_no')
    beds_by_room = {}
    for bed in all_beds:
        beds_by_room.setdefault(bed.room_no, []).append(bed)

    total_beds = all_beds.count()
    occupied_beds = all_beds.filter(status='Occupied').count()
    maintenance_beds = all_beds.filter(status='Maintenance').count()

    return render(request, 'core/bed_management.html', {
        'active_sidebar': 'dashboard',
        'beds_by_room': beds_by_room,
        'total_beds': total_beds,
        'vacant_beds': total_beds - occupied_beds - maintenance_beds,
        'occupied_beds': occupied_beds,
        'maintenance_beds': maintenance_beds,
    })


@require_module('beds', level='full')
def bed_add(request):
    """Add a single bed or bulk-add beds for a room."""
    if request.method == 'POST':
        bulk_room = request.POST.get('bulk_room', '').strip()
        bulk_count_str = request.POST.get('bulk_count', '').strip()

        # Bulk add path
        if bulk_room and bulk_count_str:
            try:
                bulk_count = int(bulk_count_str)
                if bulk_count < 1 or bulk_count > 20:
                    raise ValueError
            except ValueError:
                messages.error(request, 'Bulk count must be between 1 and 20.')
                return redirect('core:bed_manage')

            created = 0
            for i in range(1, bulk_count + 1):
                _, made = Bed.objects.get_or_create(
                    room_no=bulk_room,
                    bed_no=str(i),
                    defaults={'status': 'Vacant'},
                )
                if made:
                    created += 1

            if created:
                messages.success(request, f'{created} bed(s) added to Room {bulk_room}.')
            else:
                messages.warning(request, f'All beds in Room {bulk_room} already exist.')
            return redirect('core:bed_manage')

        # Single add path
        room_no = request.POST.get('room_no', '').strip()
        bed_no = request.POST.get('bed_no', '').strip()
        status = request.POST.get('status', 'Vacant')

        if not room_no or not bed_no:
            messages.error(request, 'Room No. and Bed No. are required.')
            return redirect('core:bed_manage')

        _, created = Bed.objects.get_or_create(
            room_no=room_no,
            bed_no=bed_no,
            defaults={'status': status},
        )
        if created:
            messages.success(request, f'Bed {bed_no} added to Room {room_no}.')
        else:
            messages.warning(request, f'Bed {bed_no} in Room {room_no} already exists.')

    return redirect('core:bed_manage')


@require_module('beds', level='full')
def bed_edit(request, pk):
    """Edit an existing bed's room, number, or status."""
    bed = get_object_or_404(Bed, pk=pk)

    if request.method == 'POST':
        bed.room_no = request.POST.get('room_no', bed.room_no).strip()
        bed.bed_no = request.POST.get('bed_no', bed.bed_no).strip()
        bed.status = request.POST.get('status', bed.status)
        bed.save()
        messages.success(request, f'Bed {bed.bed_no} (Room {bed.room_no}) updated.')
        return redirect('core:bed_manage')

    return render(request, 'core/bed_edit.html', {
        'active_sidebar': 'dashboard',
        'bed': bed,
    })


@require_module('beds', level='full')
def bed_delete(request, pk):
    """Delete a bed (POST only)."""
    if request.method == 'POST':
        bed = get_object_or_404(Bed, pk=pk)
        label = f'Bed {bed.bed_no}, Room {bed.room_no}'
        bed.delete()
        messages.success(request, f'{label} removed.')
    return redirect('core:bed_manage')