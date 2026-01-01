from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm

# User model reference (custom user models)
User = get_user_model()


# REGISTRATION FORM
class CustomUserCreationForm(UserCreationForm):
    # Required profile fields captured at sign-up
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)
    email = forms.EmailField(required=True)

    class Meta:
        # Bind the form to the active User model
        model = User
        # Form field order
        fields = ("first_name", "last_name", "email", "password1", "password2")

    def clean_email(self):
        """
        Normalise the email and enforce uniqueness.
        """
        email = (self.cleaned_data.get("email") or "").strip().lower()

        # Email is required
        if not email:
            raise forms.ValidationError("Email is required.")

        # Prevent duplicate accounts
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with this "
                                        "email already exists.")

        return email

    def save(self, commit=True):
        """
        Create the user and set username = email for email-based sign-in.
        """
        # Build user instance first so we can set fields before saving
        user = super().save(commit=False)

        # Use email as the login identifier
        user.username = (self.cleaned_data.get("email") or "").strip().lower()

        # Persist profile fields
        user.first_name = self.cleaned_data.get("first_name")
        user.last_name = self.cleaned_data.get("last_name")
        user.email = self.cleaned_data.get("email")

        # Save only if requested
        if commit:
            user.save()

        return user


# LOGIN FORM
class CustomAuthenticationForm(AuthenticationForm):
    # Email-based username field
    username = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={"autofocus": True,
                                       "class": "form-control"}),
    )

    # Password field
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
    )

    def clean_username(self):
        """
        Normalise the email and provide
        a clear error if no matching account exists.
        """
        email = (self.cleaned_data.get("username") or "").strip().lower()

        # Friendly validation before authentication runs
        if not User.objects.filter(email=email).exists():
            raise forms.ValidationError("No account found with this email.")

        return email
