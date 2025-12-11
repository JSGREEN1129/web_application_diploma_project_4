from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User

# Custom user registration form extending Django's built-in UserCreationForm


class CustomUserCreationForm(UserCreationForm):
    # Add additional required fields
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)
    email = forms.EmailField(required=True)

    class Meta:
        # Use the built-in User model
        model = User
        # Limit the fields to only what's necessary for registration
        fields = ('first_name', 'last_name', 'email', 'password1', 'password2')

    def save(self, commit=True):
        """
        Override the default save method to:
        - Prevent duplicate email registrations
        - Assign additional fields to the user before saving
        """
        email = self.cleaned_data['email']
        # Check for duplicate emails
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError(
                "A user with this email already exists.")

        # Create the user object but don't save to DB yet
        user = super().save(commit=False)
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.email = self.cleaned_data['email']  # Save the email
        if commit:
            user.save()  # Save to DB if commit=True

        return user

# Custom login form that uses email instead of usernam


class CustomAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(label='Email', widget=forms.EmailInput(
        attrs={'autofocus': True, 'class': 'form-control'}))

    # Customise password input field styling
    password = forms.CharField(label='Password',
                               strip=False, widget=forms.PasswordInput(
                                    attrs={'class': 'form-control'}))

    def clean_username(self):
        """
        Override to check that an account exists with the given email.
        If not, raise a validation error.
        """
        username = self.cleaned_data.get('username')
        # Ensure we are checking the email in
        # the User model instead of username
        if not User.objects.filter(email=username).exists():
            raise forms.ValidationError("No account found with this email.")
        return username