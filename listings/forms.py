from unicodedata import name
from django import forms

from .models import Listing


# Keep your explicit duration choices
LISTING_DURATION_CHOICES = [
    (7, "7 days"),
    (14, "14 days"),
    (30, "30 days"),
    (60, "60 days"),
]

# Project duration options
PROJECT_DURATION_CHOICES = [
    (60, "60 days"),
    (120, "120 days"),
    (200, "200 days"),
    (365, "365 days"),
]


class ListingCreateForm(forms.ModelForm):
    """
    ListingCreateForm is used for both create/edit draft flows.

    - duration_days = how long the listing stays ACTIVE
    (marketplace visibility)
    - project_duration_days = how long the underlying project is
    expected to take (term to completion)
    """

    # Listing active duration
    duration_days = forms.TypedChoiceField(
        choices=LISTING_DURATION_CHOICES,
        coerce=int,
        label="Listing duration",
        required=True,
    )

    # Project completion duration
    project_duration_days = forms.TypedChoiceField(
        choices=PROJECT_DURATION_CHOICES,
        coerce=int,
        label="Project duration",
        required=True,
    )

    class Meta:
        model = Listing

        # The order here matches the stepper flow in the template
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

        # Explicit widgets keep everything as <select> where expected
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

        Note:
        - This applies to both ModelChoice/Choice fields and TypedChoiceFields.
        - Keeping the empty option first
        also plays nicely with your JS stepper logic.
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
            field = self.fields.get(field_name)
            if not field:
                continue

            # Works for TypedChoiceField and ModelChoice / Choice fields
            if hasattr(field, "choices"):
                choices = list(field.choices)

                # Only insert placeholder if  empty option doesn't exist
                if not choices or choices[0][0] != "":
                    field.choices = [("", placeholder)] + choices

    def clean_project_name(self):
        # Normalise whitespace so "  Old Police Station  " saves cleanly
        name = (self.cleaned_data.get("project_name") or "").strip()
        return name

    def clean_postcode_prefix(self):
        """
        Basic validation for UK postcode outcodes (SW, CF, EH, etc.)
        - Normalises to uppercase
        - Guards against obviously invalid short values
        """
        value = (
            self.cleaned_data.get("postcode_prefix") or ""
        ).strip().upper()
        if value and len(value) < 2:
            raise forms.ValidationError(
                "Please select a valid postcode prefix (e.g. SW, CF, EH)."
            )
        return value

    def clean_duration_days(self):
        """
        Safety check:
        - TypedChoiceField already coerces to int
        - This ensures only the allowed UI options are accepted
        """
        value = self.cleaned_data["duration_days"]
        allowed = {7, 14, 30, 60}
        if value not in allowed:
            raise forms.ValidationError("Select a valid listing duration.")
        return value

    def clean_project_duration_days(self):
        """
        Safety check to keep project duration within your allowed UI options.
        """
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
                    "Project duration should be greater "
                    "than or equal to the listing duration.",
                )

        return cleaned


class MultiFileInput(forms.ClearableFileInput):
    # Enables <input type="file" multiple> behaviour for Django forms
    allow_multiple_selected = True


class ListingMediaForm(forms.Form):
    """
    Separate form for uploads so you can
    validate and handle files independently
    from the listing draft fields.
    """

    images = forms.FileField(
        required=False,
        widget=MultiFileInput(
            attrs={
                "multiple": True,
                "accept": "image/jpeg,image/png,image/webp",
            }
        ),
        label="Property images",
    )

    documents = forms.FileField(
        required=False,
        widget=MultiFileInput(
            attrs={
                "multiple": True,
                "accept": ".pdf,.doc,.docx",
            }
        ),
        label="Plans / documents (PDF, DOC, DOCX)",
    )
