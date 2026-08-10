from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.response import Response
from django.db.models import Q
from django.utils import timezone
from core.rbac import has_access, VIEW

from core.models import Notification
from ipd.models import IPDAdmission
from core.models import Bed


def _parse_datetime(value):
    # expects ISO string
    if not value:
        return None
    try:
        # python fromisoformat supports timezone offsets
        return timezone.datetime.fromisoformat(value)
    except Exception:
        return None


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@throttle_classes([ScopedRateThrottle])
def alerts_signal(request):
    """Lightweight polling endpoint used by dashboard to trigger alerts."""
    # RBAC check: user must have at least view access to dashboard module
    if not has_access(request.user, 'dashboard', level=VIEW):
        return Response({'error': 'Unauthorized: Your role does not have access to alerts.'}, status=403)

    user = request.user if request.user and request.user.is_authenticated else None

    # Use query params to allow client-side markers (optional)
    last_notification_pk = request.GET.get("last_notification_pk")
    try:
        last_notification_pk = int(last_notification_pk) if last_notification_pk is not None else 0
    except ValueError:
        last_notification_pk = 0

    last_icu_seen_at = request.GET.get("last_icu_seen_at")
    last_icu_seen_dt = _parse_datetime(last_icu_seen_at)

    # 1) Unread notifications for this user (or global/unassigned ones)
    notif_qs = Notification.objects.filter(is_read=False).order_by('-created_at')
    if user:
        notif_qs = notif_qs.filter(Q(user=user) | Q(user__isnull=True))
    else:
        notif_qs = notif_qs.filter(user__isnull=True)

    notifications = []
    for n in notif_qs[:8]:
        if n.pk > last_notification_pk:
            notifications.append({
                'pk': n.pk,
                'title': n.title,
                'message': n.message,
                'kind': n.notification_type,
                'created_at': n.created_at.isoformat(),
            })

    # 2) Emergency/ICU signals
    # Trigger if:
    #   a) new IPDAdmission with category=ICU created_at newer than marker
    #   b) OR any Bed.status changes (occupied) for an ICU admission
    # Since we don't have Bed history here, we approximate with:
    #   - latest ICU admission created_at
    #   - if there is a bed currently occupied by an ICU patient newer than marker, also trigger.

    now = timezone.localtime()

    latest_icu_adm = IPDAdmission.objects.filter(
        category='ICU',
        status='Admitted',
    ).order_by('-created_at').first()

    # bed-based ICU: if bed occupied and its patient has an ICU admitted admission
    bed_icu_patient_ids = []
    bed_icu_recent = None
    beds = Bed.objects.filter(status='Occupied').select_related('patient')
    for b in beds:
        if not b.patient:
            continue
        # check if patient currently has an ICU admitted admission
        icu_adm = IPDAdmission.objects.filter(
            patient=b.patient,
            category='ICU',
            status='Admitted',
        ).order_by('-created_at').first()
        if icu_adm:
            bed_icu_recent = icu_adm if (bed_icu_recent is None or icu_adm.created_at > bed_icu_recent.created_at) else bed_icu_recent

    # Choose the newest between admission-based and bed-based
    chosen = latest_icu_adm
    if bed_icu_recent and (chosen is None or bed_icu_recent.created_at > chosen.created_at):
        chosen = bed_icu_recent

    icu = None
    if chosen:
        chosen_dt = chosen.created_at
        if last_icu_seen_dt is None or chosen_dt > last_icu_seen_dt:
            icu = {
                'seen_at': chosen_dt.isoformat(),
                'title': 'Emergency / ICU',
                'patient_name': chosen.patient.name,
            }

    return Response({
        'notifications': notifications,
        'icu': icu,
        'server_time': now.isoformat(),
    })


alerts_signal.throttle_scope = 'alerts'



