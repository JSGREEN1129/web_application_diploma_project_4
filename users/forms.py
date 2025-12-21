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

LISTING_DURATION_CHOICES = [
    (7, "7 days"),
    (14, "14 days"),
    (30, "30 days"),
    (60, "60 days"),
]

PROJECT_DURATION_CHOICES = [
    (60, "60 days"),
    (120, "120 days"),
    (200, "200 days"),
    (365, "365 days"),
]


class ListingCreateForm(forms.ModelForm):
    """
    - duration_days = listing active duration (marketplace visibility)
    - project_duration_days = project duration (term to completion)
    """

    duration_days = forms.TypedChoiceField(
        choices=LISTING_DURATION_CHOICES,
        coerce=int,
        label="Listing duration",
        required=True,
    )

    project_duration_days = forms.TypedChoiceField(
        choices=PROJECT_DURATION_CHOICES,
        coerce=int,
        label="Project duration",
        required=True,
    )

    class Meta:
        model = Listing
        fields = [
            "project_name",
            "project_duration_days",  
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

    def __init__(self, *args, **kwargs):
        """
        Add a blank placeholder option to every dropdown so the browser
        doesn't auto-select the first option and falsely mark steps complete.
        """
        super().__init__(*args, **kwargs)

        placeholders = {
            "project_duration_days": "Select project duration",
            "source_use": "Select source use",
            "target_use": "Select target use",
            "country": "Select country",
            "county": "Select county",
            "postcode_prefix": "Select postcode prefix",
            "funding_band": "Select funding band",
            "return_type": "Select return type",
            "return_band": "Select return band",
            "duration_days": "Select listing duration",
        }

        for field_name, placeholder in placeholders.items():
            if field_name not in self.fields:
                continue

            field = self.fields[field_name]

            if hasattr(field, "choices"):
                existing = list(field.choices)
                if not existing or existing[0][0] != "":
                    field.choices = [("", placeholder)] + existing
            else:
                widget_choices = list(getattr(field.widget, "choices", []) or [])
                if not widget_choices or widget_choices[0][0] != "":
                    field.widget.choices = [("", placeholder)] + widget_choices

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
        allowed = {7, 14, 30, 60}
        if value not in allowed:
            raise forms.ValidationError("Select a valid listing duration.")
        return value

    def clean_project_duration_days(self):
        value = self.cleaned_data["project_duration_days"]
        allowed = {60, 120, 200, 365}
        if value not in allowed:
            raise forms.ValidationError("Select a valid project duration.")
        return value

    def clean(self):
        """
        Cross-field validation:
        - Project duration should be >= listing duration (generally expected).
        """
        cleaned = super().clean()
        listing_days = cleaned.get("duration_days")
        project_days = cleaned.get("project_duration_days")

        if listing_days is not None and project_days is not None:
            if project_days < listing_days:
                self.add_error(
                    "project_duration_days",
                    "Project duration should be greater than or equal to the listing duration.",
                )
        return cleaned


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
