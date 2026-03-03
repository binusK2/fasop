from .models import DeviceType, Device
from django.db.models.functions import Trim

def device_types(request):
    return {
        'navbar_device_types': DeviceType.objects.all()
    }

def lokasi_list(request):
    lokasi = (
        Device.objects
        .filter(is_deleted=False)
        .exclude(lokasi__isnull=True)
        .exclude(lokasi__exact='')
        .exclude(lokasi__iexact='none')
        .annotate(lokasi_clean=Trim('lokasi'))
        .values_list('lokasi_clean', flat=True)
        .distinct()
        .order_by('lokasi_clean')
    )

    return {
        'navbar_lokasi_list': lokasi
    }