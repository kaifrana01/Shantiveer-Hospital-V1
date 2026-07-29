import logging
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordResetDoneView, PasswordResetCompleteView
from django.contrib import messages
from django.urls import reverse_lazy
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
from django.core.cache import cache
from django.contrib.auth.views import PasswordResetConfirmView
from django.views.decorators.http import require_POST

from .forms import StyledLoginForm, ForgotPasswordForm, StyledPasswordChangeForm, StyledSetPasswordForm, ChangeEmailForm, UserBasicForm, UserProfileForm
from .models import UserProfile

logger = logging.getLogger(__name__)
_MAX_ATTEMPTS = getattr(settings, 'LOGIN_ATTEMPTS_LIMIT', 5)
_LOCKOUT_SECS = getattr(settings, 'LOGIN_LOCKOUT_DURATION', 300)


def _ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    return xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR', '')

def _locked(ip):
    try:
        return bool(cache.get(f'hms:login_lock:{ip}'))
    except Exception:
        return False  # cache unavailable — allow login rather than locking everyone out

def _fail(ip):
    try:
        k = f'hms:login_fail:{ip}'
        n = cache.get(k, 0) + 1
        cache.set(k, n, timeout=_LOCKOUT_SECS)
        if n >= _MAX_ATTEMPTS:
            cache.set(f'hms:login_lock:{ip}', True, timeout=_LOCKOUT_SECS)
            logger.warning('Login locked IP %s after %d attempts', ip, n)
    except Exception:
        logger.warning('Cache unavailable — login brute-force protection disabled temporarily')

def _clear(ip):
    try:
        cache.delete(f'hms:login_fail:{ip}')
        cache.delete(f'hms:login_lock:{ip}')
    except Exception:
        pass


def _role_redirect(user):
    """Send each role to its natural landing page after login."""
    if user.is_superuser or user.groups.filter(name='Admin').exists():
        return redirect('core:dashboard')
    if user.groups.filter(name='Accountant').exists():
        return redirect('core:dashboard')

    if user.groups.filter(name='Doctor').exists():
        return redirect('core:dashboard')           # doctor dashboard
    if user.groups.filter(name='Receptionist').exists():
        return redirect('opd:registration')         # receptionist → OPD desk
    if user.groups.filter(name='Pharmacist').exists():
        return redirect('pharmacy:items')           # pharmacist → inventory
    return redirect('core:home')


def _role_from_hint(hint: str):
    """Map login.html role_hint to a redirect target.

    role_hint values come from the frontend:
    - admin / doctor / receptionist / pharmacist

    We translate them into the group-based redirect behavior.
    """
    if not hint:
        return None

    hint = hint.strip().lower()
    mapping = {
        'admin': 'Admin',
        'doctor': 'Doctor',
        'receptionist': 'Receptionist',
        'pharmacist': 'Pharmacist',
        'accountant': 'Accountant',
    }

    return mapping.get(hint)


def login_view(request):
    if request.user.is_authenticated:
        return _role_redirect(request.user)

    ip = _ip(request)
    if _locked(ip):
        return render(
            request,
            'accounts/login.html',
            {'form': StyledLoginForm(), 'locked': True},
        )

    form = StyledLoginForm(request, data=request.POST or None)

    if request.method == 'POST':
        username_in = (request.POST.get('username') or '').strip()
        password_in = request.POST.get('password') or ''

        # Explicitly check whether the credentials can authenticate.
        # - If user doesn't exist: authentication should fail.
        # - If user exists but password doesn't match: authentication should fail.
        # (Still keep the same generic UI message for security.)
        try:
            user_candidates = User.objects.filter(username__iexact=username_in)
            if not user_candidates.exists() and '@' in username_in:
                user_candidates = User.objects.filter(email__iexact=username_in)

            candidate = user_candidates.first() if user_candidates.exists() else None
            password_matches = bool(candidate and candidate.check_password(password_in))
        except Exception:
            candidate = None
            password_matches = False

        if form.is_valid() and candidate and password_matches:
            user = candidate
            _clear(ip)
            login(request, user)
            messages.success(request, f'Welcome, {user.get_full_name() or user.username}!')

            selected_group = _role_from_hint(request.POST.get('role_hint', ''))
            if selected_group and user.groups.filter(name=selected_group).exists():
                return _role_redirect(user)

            return _role_redirect(user)

        _fail(ip)

    return render(request, 'accounts/login.html', {'form': form})





@require_POST
def logout_view(request):
    """Logout requires POST to prevent CSRF-based forced logout via GET links."""
    logout(request)
    return redirect('accounts:login')


def forgot_password_view(request):
    if request.user.is_authenticated:
        return redirect('core:home')

    # Rate-limit by IP — same mechanism as login brute-force protection.
    # 5 requests per lockout window prevents email enumeration via timing.
    ip = _ip(request)
    if _locked(ip):
        messages.error(request, 'Too many requests. Please try again in a few minutes.')
        return render(request, 'accounts/forgot_password.html', {'form': ForgotPasswordForm(), 'locked': True})

    form = ForgotPasswordForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        _fail(ip)   # count every submission, even valid ones, to prevent enumeration
        email = form.cleaned_data['email']
        for user in User.objects.filter(email__iexact=email):
            uid   = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            url   = request.build_absolute_uri(
                reverse_lazy('accounts:password_reset_confirm',
                             kwargs={'uidb64': uid, 'token': token}))
            try:
                send_mail('ShantiVeer HMS — Password Reset',
                          f'Reset link:\n{url}\n(expires in 24h)',
                          settings.DEFAULT_FROM_EMAIL, [user.email])
            except Exception as e:
                logger.error('Reset mail failed: %s', e)
        # Always show the same message whether email exists or not
        messages.success(request, 'If that email is registered, a reset link has been sent.')
        return redirect('accounts:password_reset_done')
    return render(request, 'accounts/forgot_password.html', {'form': form})


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'accounts/password_reset_confirm.html'
    form_class    = StyledSetPasswordForm
    success_url   = reverse_lazy('accounts:password_reset_complete')


@login_required
def change_email_view(request):
    form = ChangeEmailForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        # Use form.cleaned_data — validated and sanitized by the form
        current_password = form.cleaned_data['current_password']
        if not request.user.check_password(current_password):
            messages.error(request, 'Current password is incorrect.')
            return render(request, 'accounts/change_email.html', {'form': form})
        request.user.email = form.cleaned_data['new_email']
        request.user.save()
        messages.success(request, 'Email updated successfully.')
        return redirect('accounts:change_password')
    return render(request, 'accounts/change_email.html', {'form': form})


@login_required
def change_password_view(request):
    form = StyledPasswordChangeForm(request.user, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        update_session_auth_hash(request, form.save())
        messages.success(request, 'Password changed.')
        return redirect('core:home')
    return render(request, 'accounts/change_password.html', {'form': form})


@login_required
def profile_view(request):
    """View own profile — read-only overview with tab switching."""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    role = request.user.groups.all().first()
    return render(request, 'accounts/profile.html', {
        'profile': profile,
        'role': role,
        'active_sidebar': 'profile',
    })


@login_required
def profile_edit_view(request):
    """Edit own profile — personal details, employment, documents."""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        u_form = UserBasicForm(request.POST, instance=request.user)
        p_form = UserProfileForm(request.POST, request.FILES, instance=profile)
        if u_form.is_valid() and p_form.is_valid():
            u_form.save()
            p_form.save()
            messages.success(request, 'Profile updated successfully.')
            return redirect('accounts:profile')
    else:
        u_form = UserBasicForm(instance=request.user)
        p_form = UserProfileForm(instance=profile)
    return render(request, 'accounts/profile_edit.html', {
        'u_form': u_form,
        'p_form': p_form,
        'profile': profile,
        'active_sidebar': 'profile',
    })
