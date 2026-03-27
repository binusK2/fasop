from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash
from django.contrib import messages


@login_required
def force_change_password(request):
    """
    Halaman ganti password wajib (first login).
    Jika user tidak perlu ganti password, redirect ke dashboard.
    """
    profile = getattr(request.user, 'profile', None)

    # Jika tidak perlu ganti password, langsung ke dashboard
    if profile and not profile.force_password_change:
        return redirect('dashboard')

    error = ''

    if request.method == 'POST':
        new_password1 = request.POST.get('new_password1', '').strip()
        new_password2 = request.POST.get('new_password2', '').strip()

        if not new_password1 or not new_password2:
            error = 'Semua field harus diisi.'
        elif new_password1 != new_password2:
            error = 'Password baru tidak cocok.'
        elif len(new_password1) < 8:
            error = 'Password minimal 8 karakter.'
        else:
            # Validate password with Django validators
            from django.contrib.auth.password_validation import validate_password
            try:
                validate_password(new_password1, request.user)
            except Exception as e:
                error = '; '.join(e.messages)

            if not error:
                request.user.set_password(new_password1)
                request.user.save()
                # Matikan flag force_password_change
                if profile:
                    profile.force_password_change = False
                    profile.save()
                # Update session agar tidak logout
                update_session_auth_hash(request, request.user)
                messages.success(request, 'Password berhasil diubah! Selamat datang di FASOP.')
                return redirect('dashboard')

    return render(request, 'registration/force_change_password.html', {
        'error': error,
    })
