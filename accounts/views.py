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
from core.rbac import get_user_role, ADMIN, DOCTOR, RECEPTIONIST, PHARMACIST, ACCOUNTANT, NURSE, LAB_TECH, BILLING

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
    role = get_user_role(user)
    if role == RECEPTIONIST:
        return redirect('opd:registration')     # receptionist → OPD desk
    if role == PHARMACIST:
        return redirect('pharmacy:items')        # pharmacist → inventory
    if role == LAB_TECH:
        return redirect('lab:view_all')          # lab tech → lab list
    if role == BILLING:
        return redirect('ipd:payment')           # billing clerk → payment screen
    # Admin, Doctor, Nurse, Accountant and unrecognised roles → dashboard
    return redirect('core:dashboard')


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

        # BUG-27 FIX: use Django's authenticate() as the single source of
        # truth for credential validation.  The previous approach called
        # form.is_valid() (which runs authenticate() internally) AND also
        # manually checked candidate.check_password() — the latter bypasses
        # any custom auth backends (e.g. 2FA, account-disabled checks).
        # Now we rely solely on form.is_valid() / authenticate(), and only
        # do a direct DB lookup to resolve login-by-email before handing
        # off to the form.  The form's authenticate() call will enforce all
        # backend checks.

        # Support login by email: resolve the email to a username first so
        # Django's ModelBackend can authenticate against the username field.
        resolved_username = username_in
        if '@' in username_in:
            email_user = User.objects.filter(email__iexact=username_in).first()
            if email_user:
                resolved_username = email_user.username

        # Re-bind the form with the resolved username so authenticate() works.
        post_data = request.POST.copy()
        post_data['username'] = resolved_username
        form = StyledLoginForm(request, data=post_data)

        if form.is_valid():
            user = form.get_user()
            _clear(ip)
            login(request, user)
            messages.success(request, f'Welcome, {user.get_full_name() or user.username}!')
            return _role_redirect(user)

        _fail(ip)
        # Re-render with original POST (show original username in the field)
        form = StyledLoginForm(request, data=request.POST)

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
    from core.rbac import ROLE_LABELS
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    role = get_user_role(request.user)
    role_label = ROLE_LABELS.get(role, 'User')
    return render(request, 'accounts/profile.html', {
        'profile': profile,
        'role': role_label,
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
