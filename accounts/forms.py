from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, SetPasswordForm
from django.contrib.auth.models import User
from .models import UserProfile


class StyledLoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={
        'class': 'form-control', 'placeholder': 'Username',
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-control', 'placeholder': 'Password',
    }))


class ForgotPasswordForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={
        'class': 'form-control', 'placeholder': 'Registered email address',
    }))


class StyledSetPasswordForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})


class StyledPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})


class ChangeEmailForm(forms.Form):
    current_password = forms.CharField(
        label='Current Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your current password',
        })
    )
    new_email = forms.EmailField(
        label='New Email Address',
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter new email address',
        })
    )
    confirm_email = forms.EmailField(
        label='Confirm Email Address',
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm new email address',
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        new_email = cleaned_data.get('new_email')
        confirm_email = cleaned_data.get('confirm_email')
        if new_email and confirm_email and new_email != confirm_email:
            raise forms.ValidationError('Email addresses do not match.')
        if new_email and User.objects.filter(email__iexact=new_email).exists():
            raise forms.ValidationError('This email address is already in use.')
        return cleaned_data


class UserBasicForm(forms.ModelForm):
    """Editable fields from Django's User model."""
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name':  forms.TextInput(attrs={'class': 'form-control'}),
            'email':      forms.EmailInput(attrs={'class': 'form-control'}),
        }


class UserProfileForm(forms.ModelForm):
    """All UserProfile fields."""
    class Meta:
        model = UserProfile
        exclude = ['user', 'updated_at']
        widgets = {
            'phone':             forms.TextInput(attrs={'class': 'form-control'}),
            'alternate_phone':   forms.TextInput(attrs={'class': 'form-control'}),
            'date_of_birth':     forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'gender':            forms.Select(attrs={'class': 'form-select'}),
            'blood_group':       forms.Select(attrs={'class': 'form-select'}),
            'address':           forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'emergency_contact': forms.TextInput(attrs={'class': 'form-control'}),
            'profile_photo':     forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'designation':       forms.TextInput(attrs={'class': 'form-control'}),
            'department':        forms.TextInput(attrs={'class': 'form-control'}),
            'specialization':    forms.TextInput(attrs={'class': 'form-control'}),
            'qualification':     forms.TextInput(attrs={'class': 'form-control'}),
            'employee_code':     forms.TextInput(attrs={'class': 'form-control'}),
            'joining_date':      forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'username_handle':   forms.TextInput(attrs={'class': 'form-control', 'placeholder': '@handle'}),
            'document_1':        forms.FileInput(attrs={'class': 'form-control'}),
            'document_1_name':   forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Aadhaar Card'}),
            'document_2':        forms.FileInput(attrs={'class': 'form-control'}),
            'document_2_name':   forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Degree Certificate'}),
            'document_3':        forms.FileInput(attrs={'class': 'form-control'}),
            'document_3_name':   forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Registration Certificate'}),
        }
