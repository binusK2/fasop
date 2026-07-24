from devices.models import UserProfile


def whitelist_operator(request, credentials):
    """Akun role Operator dipakai bersama banyak orang — jangan pernah dikunci django-axes."""
    username = (credentials or {}).get('username')
    if not username:
        return False
    return UserProfile.objects.filter(user__username=username, role='operator').exists()
