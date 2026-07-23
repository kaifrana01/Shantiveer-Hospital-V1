from django.urls import reverse
from core.models import Notification


def is_low_stock(item):
    return item.stock <= item.buffer


def sync_pharmacy_stock_notifications():
    from pharmacy.models import PharmacyItem

    active_refs = set()
    for item in PharmacyItem.objects.filter(is_active=True):
        if is_low_stock(item):
            ref = f'pharmacy_low_{item.pk}'
            active_refs.add(ref)
            Notification.objects.get_or_create(
                reference_id=ref,
                defaults={
                    'title': f'Low Stock: {item.name}',
                    'message': (
                        f'{item.name} has only {item.stock} units left '
                        f'(buffer: {item.buffer}). Please reorder immediately.'
                    ),
                    'notification_type': Notification.TYPE_PHARMACY_LOW,
                    'link': reverse('pharmacy:items'),
                },
            )
    Notification.objects.filter(
        notification_type=Notification.TYPE_PHARMACY_LOW,
    ).exclude(reference_id__in=active_refs).update(is_read=True)


def notify_prescription_medicine(line):
    from pharmacy.models import PharmacyItem

    item = line.pharmacy_item
    stock_msg = ''
    ntype = Notification.TYPE_PRESCRIPTION
    if item and is_low_stock(item):
        stock_msg = f' Only {item.stock} in stock (required: {line.quantity}).'
        line.status = line.STATUS_LOW_STOCK
        line.save(update_fields=['status'])

    ref = f'prescription_med_{line.pk}'
    Notification.objects.get_or_create(
        reference_id=ref,
        defaults={
            'title': f'Medicine required: {line.medicine_name}',
            'message': (
                f'Patient {line.prescription.patient.name} (UHID {line.prescription.patient.uhid}) '
                f'needs {line.medicine_name} x{line.quantity}.{stock_msg}'
            ),
            'notification_type': ntype,
            'link': reverse('prescription:detail', args=[line.prescription.opd_visit_id]),
        },
    )


def match_pharmacy_item(medicine_name):
    from pharmacy.models import PharmacyItem
    name = medicine_name.strip()
    item = PharmacyItem.objects.filter(name__iexact=name, is_active=True).first()
    if item:
        return item
    return PharmacyItem.objects.filter(name__icontains=name.split()[0], is_active=True).first()
