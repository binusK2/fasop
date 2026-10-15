from fasop.client_ip import ip_klien

from .models import AuditLog


def log_action(request, action, app_label, model_name, object_id=None, object_repr='', detail=''):
    """
    Catat satu entri audit log.
    Aman dipanggil dari mana saja — error tidak akan mengganggu request utama.
    """
    try:
        ip = ip_klien(request)

        AuditLog.objects.create(
            user        = request.user if request.user.is_authenticated else None,
            action      = action,
            app_label   = app_label,
            model_name  = model_name,
            object_id   = object_id,
            object_repr = str(object_repr)[:255],
            detail      = detail,
            ip_address  = ip,
        )
    except Exception:
        pass
