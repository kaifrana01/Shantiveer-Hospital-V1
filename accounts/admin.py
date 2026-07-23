from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth.models import User, Group
from django import forms
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from django.contrib.admin.models import LogEntry, ADDITION, CHANGE, DELETION
from django.utils import timezone


# ─── HMS role group names (in addition to Django's built-in groups) ───────────
HMS_GROUPS = [
    'Doctor', 'Administration', 'Receptionist',
    'Nurse', 'LabTech', 'Pharmacist', 'Accountant', 'Admin',
]

ACTION_LABELS = {
    ADDITION: ('Added',   'success'),
    CHANGE:   ('Changed', 'warning'),
    DELETION: ('Deleted', 'danger'),
}
ACTION_ICONS = {
    ADDITION: 'bi-plus-circle-fill',
    CHANGE:   'bi-pencil-fill',
    DELETION: 'bi-trash-fill',
}


# ─── Role-aware User Creation Form ────────────────────────────────────────────

class HMSUserCreationForm(UserCreationForm):
    role_group = forms.ChoiceField(
        label='Role / Group',
        choices=[('', '— Select Role —')] + [(g, g) for g in HMS_GROUPS],
        required=False,
        help_text='Assign this user to a hospital role group. '
                  'Roles control which HMS menus the user can access.',
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'first_name', 'last_name', 'email')

    def save(self, commit=True):
        user = super().save(commit=commit)

        def _assign_role():
            role = self.cleaned_data.get('role_group')
            if role:
                try:
                    user.groups.set([Group.objects.get(name=role)])
                except Group.DoesNotExist:
                    pass

        if commit:
            _assign_role()
        else:
            # Django admin always calls save(commit=False) then save_m2m().
            # Chain our group assignment after the existing save_m2m so it runs.
            _original_save_m2m = getattr(self, 'save_m2m', lambda: None)
            def _save_m2m():
                _original_save_m2m()
                _assign_role()
            self.save_m2m = _save_m2m

        return user


class HMSUserChangeForm(UserChangeForm):
    role_group = forms.ChoiceField(
        label='Role / Group',
        choices=[('', '— No Role —')] + [(g, g) for g in HMS_GROUPS],
        required=False,
        help_text='Change the HMS role for this user.',
    )

    class Meta(UserChangeForm.Meta):
        model = User
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            grps = list(self.instance.groups.values_list('name', flat=True))
            self.fields['role_group'].initial = grps[0] if grps else ''

    def save(self, commit=True):
        user = super().save(commit=commit)

        def _assign_role():
            role = self.cleaned_data.get('role_group')
            if role:
                try:
                    user.groups.set([Group.objects.get(name=role)])
                except Group.DoesNotExist:
                    user.groups.clear()
            else:
                user.groups.clear()

        if commit:
            _assign_role()
        else:
            _original_save_m2m = getattr(self, 'save_m2m', lambda: None)
            def _save_m2m():
                _original_save_m2m()
                _assign_role()
            self.save_m2m = _save_m2m

        return user


# ─── User Admin ───────────────────────────────────────────────────────────────

class HMSUserAdmin(DjangoUserAdmin):
    form = HMSUserChangeForm
    add_form = HMSUserCreationForm

    list_display = (
        'username', 'full_name_col', 'email',
        'role_badge', 'status_badge', 'last_login', 'date_joined',
    )
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'groups', 'date_joined')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    ordering = ('-date_joined',)
    list_per_page = 25

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'email')}),
        (_('HMS Role'), {
            'fields': ('role_group',),
            'description': (
                'Select the single HMS role for this user. '
                '<b>Doctor</b> — clinical access &nbsp;|&nbsp; '
                '<b>Receptionist / Administration</b> — front-desk &nbsp;|&nbsp; '
                '<b>Admin</b> — full access.'
            ),
        }),
        (_('Account status'), {'fields': ('is_active', 'is_staff', 'is_superuser')}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'username', 'first_name', 'last_name', 'email',
                'password1', 'password2', 'role_group',
            ),
        }),
    )
    readonly_fields = ('last_login', 'date_joined')

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('groups')

    # ── Custom columns ────────────────────────────────────────────────────────

    def full_name_col(self, obj):
        name = obj.get_full_name()
        return name.strip() or '—'
    full_name_col.short_description = 'Full Name'

    def role_badge(self, obj):
        colours = {
            'Doctor':         ('#1d4ed8', '#dbeafe'),
            'Administration': ('#166534', '#dcfce7'),
            'Receptionist':   ('#0e7490', '#cffafe'),
            'Nurse':          ('#c2410c', '#ffedd5'),
            'LabTech':        ('#5b21b6', '#ede9fe'),
            'Pharmacist':     ('#065f46', '#d1fae5'),
            'Accountant':   ('#713f12', '#fef9c3'),
            'Admin':          ('#991b1b', '#fee2e2'),
        }
        if obj.is_superuser:
            return format_html(
                '<span style="background:#f3e8ff;color:#6b21a8;padding:2px 9px;'
                'border-radius:12px;font-size:11px;font-weight:600">'
                '<i class="bi bi-shield-fill-check"></i> Superuser</span>'
            )
        grps = list(obj.groups.values_list('name', flat=True))
        if grps:
            fg, bg = colours.get(grps[0], ('#374151', '#f1f5f9'))
            return format_html(
                '<span style="background:{};color:{};padding:2px 9px;'
                'border-radius:12px;font-size:11px;font-weight:600">{}</span>',
                bg, fg, grps[0],
            )
        return format_html('<span style="color:#aaa;font-size:11px">No Role</span>')
    role_badge.short_description = 'Role'

    def status_badge(self, obj):
        if obj.is_active:
            return format_html(
                '<span style="background:#d1fae5;color:#065f46;padding:2px 9px;'
                'border-radius:12px;font-size:11px">● Active</span>'
            )
        return format_html(
            '<span style="background:#fee2e2;color:#991b1b;padding:2px 9px;'
            'border-radius:12px;font-size:11px">● Inactive</span>'
        )
    status_badge.short_description = 'Status'


# ─── Activity Log Admin ───────────────────────────────────────────────────────

class ActivityLogAdmin(admin.ModelAdmin):
    """Read-only viewer for Django's built-in admin log (who changed what & when)."""

    list_display = (
        'action_time_col', 'user_col', 'action_type_col',
        'model_col', 'object_col', 'changes_col',
    )
    list_filter   = ('action_flag', 'content_type', 'action_time')
    search_fields = ('user__username', 'user__first_name', 'user__last_name',
                     'object_repr', 'change_message')
    date_hierarchy = 'action_time'
    list_per_page  = 40
    ordering       = ('-action_time',)
    readonly_fields = (
        'action_time', 'user', 'content_type', 'object_id',
        'object_repr', 'action_flag', 'change_message',
    )

    def has_add_permission(self, request):      return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return request.user.is_superuser

    def action_time_col(self, obj):
        lt = timezone.localtime(obj.action_time)
        return format_html(
            '<span style="white-space:nowrap;font-size:12px">'
            '<b>{}</b><br><span style="color:#888">{}</span></span>',
            lt.strftime('%d %b %Y'), lt.strftime('%H:%M:%S'),
        )
    action_time_col.short_description = 'Date & Time'
    action_time_col.admin_order_field = 'action_time'

    def user_col(self, obj):
        name = obj.user.get_full_name() or obj.user.username
        grps = list(obj.user.groups.values_list('name', flat=True))
        role = grps[0] if grps else ('Superuser' if obj.user.is_superuser else '—')
        return format_html(
            '<span style="font-size:12px"><b>{}</b><br>'
            '<span style="color:#888;font-size:11px">@{} · {}</span></span>',
            name, obj.user.username, role,
        )
    user_col.short_description = 'User'
    user_col.admin_order_field = 'user__username'

    def action_type_col(self, obj):
        label, colour = ACTION_LABELS.get(obj.action_flag, ('Unknown', 'secondary'))
        icon  = ACTION_ICONS.get(obj.action_flag, 'bi-question')
        bg = {'success': '#d1fae5', 'warning': '#fef3c7', 'danger': '#fee2e2',
              'secondary': '#f1f5f9'}
        fg = {'success': '#065f46', 'warning': '#78350f', 'danger': '#991b1b',
              'secondary': '#374151'}
        return format_html(
            '<span style="background:{};color:{};padding:3px 9px;border-radius:12px;'
            'font-size:11px;font-weight:600;white-space:nowrap">'
            '<i class="bi {}"></i> {}</span>',
            bg[colour], fg[colour], icon, label,
        )
    action_type_col.short_description = 'Action'

    def model_col(self, obj):
        if obj.content_type:
            return format_html(
                '<span style="font-size:12px"><b>{}</b><br>'
                '<span style="color:#888;font-size:11px">{}</span></span>',
                obj.content_type.model.replace('_', ' ').title(),
                obj.content_type.app_label,
            )
        return '—'
    model_col.short_description = 'Model'

    def object_col(self, obj):
        text = obj.object_repr
        short = text[:60] + ('…' if len(text) > 60 else '')
        return format_html('<span style="font-size:12px">{}</span>', short)
    object_col.short_description = 'Record'

    def changes_col(self, obj):
        msg = obj.get_change_message()
        if not msg:
            return format_html('<span style="color:#aaa;font-size:11px">—</span>')
        short = msg[:100] + ('…' if len(msg) > 100 else '')
        return format_html('<span style="font-size:11px;color:#555">{}</span>', short)
    changes_col.short_description = 'Changes'


# ─── Registration ─────────────────────────────────────────────────────────────

try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass

admin.site.register(User, HMSUserAdmin)
admin.site.register(LogEntry, ActivityLogAdmin)