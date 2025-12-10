from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth import views as auth_views
from django.shortcuts import redirect, render

from .forms import CustomUserCreationForm, CustomAuthenticationForm


def register(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Your account has been created.")
            return redirect("users:dashboard")
    else:
        form = CustomUserCreationForm()

    return render(request, "users/register.html", {"form": form})


class CustomLoginView(auth_views.LoginView):
    template_name = "users/login.html"
    authentication_form = CustomAuthenticationForm


@login_required
def dashboard(request):
    return render(request, "users/dashboard.html")
