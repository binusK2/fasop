from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Q

from .models import AuditLog


@login_required
def audit_log_list(request):
    if not request.user.is_superuser:
        return redirect('dashboard')

    qs = AuditLog.objects.select_related('user').all()

    # ── Filter ────────────────────────────────────────────────
    q          = request.GET.get('q', '').strip()
    user_id    = request.GET.get('user', '').strip()
    action     = request.GET.get('action', '').strip()
    app_label  = request.GET.get('app', '').strip()
    date_from  = request.GET.get('from', '').strip()
    date_to    = request.GET.get('to', '').strip()

    if q:
        qs = qs.filter(
            Q(object_repr__icontains=q) |
            Q(detail__icontains=q) |
            Q(model_name__icontains=q)
        )
    if user_id:
        qs = qs.filter(user_id=user_id)
    if action:
        qs = qs.filter(action=action)
    if app_label:
        qs = qs.filter(app_label=app_label)
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)

    # ── Pagination ────────────────────────────────────────────
    paginator = Paginator(qs, 50)
    page      = request.GET.get('page', 1)
    logs      = paginator.get_page(page)

    # ── Filter option lists ───────────────────────────────────
    user_list = (
        User.objects.filter(audit_logs__isnull=False)
        .distinct()
        .order_by('username')
    )
    app_list = (
        AuditLog.objects.values_list('app_label', flat=True)
        .distinct().order_by('app_label')
    )

    return render(request, 'auditlog/log_list.html', {
        'logs':           logs,
        'q':              q,
        'user_id':        user_id,
        'action':         action,
        'app_label':      app_label,
        'date_from':      date_from,
        'date_to':        date_to,
        'user_list':      user_list,
        'app_list':       app_list,
        'action_choices': AuditLog.ACTION_CHOICES,
        'total':          qs.count(),
    })
