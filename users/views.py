from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate, get_user_model
from django.views.decorators.cache import never_cache
from django.contrib import messages
from .forms import CustomUserCreationForm, CustomAuthenticationForm

User = get_user_model()

# View to handle user login
@never_cache
def login_view(request):
    login_form = CustomAuthenticationForm(request, data=request.POST or None)
    register_form = CustomUserCreationForm()

    if request.method == 'POST' and 'login_submit' in request.POST:
        email = request.POST.get('username', '').strip().lower()
        password = request.POST.get('password', '')

        # If no email or password, show generic error to avoid info leak
        if not email or not password:
            messages.error(
                request,
                "Please enter your registered email and password to login."
            )
        else:
            # Check if user with email exists
            user_exists = User.objects.filter(email=email).exists()

            if not user_exists:
                messages.error(
                    request,
                    "There is no account associated with the email address."
                )
            else:
                # User exists, check password
                user_auth = authenticate(
                    request, username=email, password=password
                )
                if user_auth is not None:
                    login(request, user_auth,
                          backend='users.backends.EmailBackend')
                    messages.success(request, "Logged in successfully!")
                    return redirect('users:dashboard')   
                else:
                    messages.error(
                        request, "You have entered your password incorrectly."
                    )

    context = {
        'login_form': login_form,
        'register_form': register_form,
        'show_form': 'login'
    }
    return render(request, 'users/login.html', context) 


# View to handle user registration
@never_cache
def register_view(request):
    login_form = CustomAuthenticationForm(request)  # Blank form for display
    register_form = CustomUserCreationForm(request.POST or None)

    if request.method == 'POST' and 'register_submit' in request.POST:
        if register_form.is_valid():
            user = register_form.save(commit=False)  # Don't save yet
            # Set username to email to ensure uniqueness
            user.username = user.email
            user.save()  # Now save to DB

            login(request, user, backend='users.backends.EmailBackend')
            messages.success(request, "Registered and logged in successfully!")
            return redirect('users:dashboard')
        else:
            messages.error(request, "Please correct the errors below.")

    context = {
        'login_form': login_form,
        'register_form': register_form,
        'show_form': 'register'  # Tell template to show register first
    }
    return render(request, 'users/register.html', context)


def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('users:login') 


def dashboard_view(request):
    # Simple placeholder dashboard view
    return render(request, 'users/dashboard.html')
