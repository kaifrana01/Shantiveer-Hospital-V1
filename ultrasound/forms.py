from django import forms

from .models import UltrasoundTestMaster


class UltrasoundBillForm(forms.Form):
    patient_name = forms.CharField(max_length=200, required=True)
    mobile = forms.CharField(max_length=15, required=False)
    address = forms.CharField(widget=forms.Textarea, required=False)
    consultant = forms.CharField(max_length=200, required=False)
    referred_by = forms.CharField(max_length=200, required=False)
    remarks = forms.CharField(widget=forms.Textarea, required=False)
    discount = forms.DecimalField(required=False, decimal_places=2, max_digits=10, initial=0)
    payment_mode = forms.CharField(max_length=20, required=False, initial='Cash')
    date = forms.DateField(required=True)

    # Render checkboxes (with customizable fee inputs) manually in the
    # template using the UltrasoundTestMaster queryset. This field is kept
    # as a placeholder for validation/back-compat.
    tests = forms.ModelMultipleChoiceField(
        queryset=UltrasoundTestMaster.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
