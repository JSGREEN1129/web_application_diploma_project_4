from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User

from .models import Listing

# USER FORMS


class CustomUserCreationForm(UserCreationForm):
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "password1", "password2")

    def save(self, commit=True):
        """
        Override the default save method to:
        - Prevent duplicate email registrations
        - Assign additional fields to the user before saving
        """
        email = self.cleaned_data["email"]
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with this email already exists.")

        user = super().save(commit=False)
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.email = email

        if commit:
            user.save()

        return user


class CustomAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={"autofocus": True, "class": "form-control"}),
    )
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
    )

    def clean_username(self):
        """
        Override to check that an account exists with the given email.
        If not, raise a validation error.
        """
        username = self.cleaned_data.get("username")
        if not User.objects.filter(email=username).exists():
            raise forms.ValidationError("No account found with this email.")
        return username


# LISTINGS FORM

DURATION_CHOICES = [
    (7, "7 days"),
    (14, "14 days"),
    (30, "30 days"),
    (60, "60 days"),
]


class ListingCreateForm(forms.ModelForm):
    """
    Form for creating a property investment listing.
    Listing is saved as DRAFT and activated after payment.
    """

    duration_days = forms.TypedChoiceField(
        choices=DURATION_CHOICES,
        coerce=int,
        label="Listing duration",
        required=True,
    )

    class Meta:
        model = Listing
        fields = [
            "source_use",
            "target_use",
            "country",
            "county",
            "postcode_prefix",
            "funding_band",
            "return_type",
            "return_band",
            "duration_days",
        ]
        widgets = {
            "source_use": forms.Select(),
            "target_use": forms.Select(),
            "country": forms.Select(),
            "county": forms.Select(),
            "postcode_prefix": forms.Select(),
            "funding_band": forms.Select(),
            "return_type": forms.Select(),
            "return_band": forms.Select(),
        }

    def clean_postcode_prefix(self):
        """
        Basic validation for UK postcode outcodes (SW, CF, EH, etc.)
        """
        value = (self.cleaned_data.get("postcode_prefix") or "").strip().upper()
        if len(value) < 2:
            raise forms.ValidationError(
                "Please select a valid postcode prefix (e.g. SW, CF, EH)."
            )
        return value

    def clean_duration_days(self):
        value = self.cleaned_data["duration_days"]
        if value not in {7, 14, 30, 60}:
            raise forms.ValidationError("Select a valid duration.")
        return value


class MultiFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class ListingMediaForm(forms.Form):
    images = forms.FileField(
        required=False,
        widget=MultiFileInput(
            attrs={"multiple": True, "accept": "image/jpeg,image/png,image/webp"}
        ),
        label="Property images",
    )

    documents = forms.FileField(
        required=False,
        widget=MultiFileInput(attrs={"multiple": True, "accept": ".pdf,.doc,.docx"}),
        label="Plans / documents (PDF, DOC, DOCX)",
    )
