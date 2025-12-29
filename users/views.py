from __future__ import annotations

from decimal import Decimal
import logging

from django.contrib import messages
from django.contrib.auth import login, logout, authenticate, get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.shortcuts import render, redirect
from django.views.decorators.cache import never_cache

from investments.models import Investment
from listings.models import Listing

from .forms import CustomUserCreationForm, CustomAuthenticationForm

# Module logger and user model reference
logger = logging.getLogger(__name__)
User = get_user_model()


# LOGIN
@never_cache
def login_view(request):
    """
    Render the login/register screen and handle login submissions.
    """
    # Forms shown on the combined login page
    login_form = CustomAuthenticationForm(request, data=request.POST or None)
    register_form = CustomUserCreationForm()

    # Login submission
    if request.method == "POST" and "login_submit" in request.POST:
        # Normalise credentials
        email = request.POST.get("username", "").strip().lower()
        password = request.POST.get("password", "")

        # Basic validation before attempting authentication
        if not email or not password:
            messages.error(request, "Please enter your registered email and password to login.")
        else:
            # Friendly message if the email is not registered
            user_exists = User.objects.filter(email=email).exists()
            if not user_exists:
                messages.error(request, "There is no account associated with the email address.")
            else:
                # Authenticate using email as the username identifier
                user_auth = authenticate(request, username=email, password=password)
                if user_auth is not None:
                    # Log the user in using the custom email backend
                    login(request, user_auth, backend="users.backends.EmailBackend")
                    messages.success(request, "Logged in successfully!")
                    return redirect("users:dashboard")
                else:
                    messages.error(request, "You have entered your password incorrectly.")

    # Default: render page
    return render(
        request,
        "users/login.html",
        {
            "login_form": login_form,
            "register_form": register_form,
            "show_form": "login",
        },
    )


# REGISTER
@never_cache
def register_view(request):
    """
    Render the login/register screen and handle registration submissions.
    """
    # Forms shown on the combined register page
    login_form = CustomAuthenticationForm(request)
    register_form = CustomUserCreationForm(request.POST or None)

    # Register submission
    if request.method == "POST" and "register_submit" in request.POST:
        if register_form.is_valid():
            # Create user without saving so we can ensure username is set
            user = register_form.save(commit=False)
            user.username = user.email
            user.save()

            # Auto-login after successful registration
            login(request, user, backend="users.backends.EmailBackend")
            messages.success(request, "Registered and logged in successfully!")
            return redirect("users:dashboard")
        else:
            messages.error(request, "Please correct the errors below.")

    # Default: render page
    return render(
        request,
        "users/register.html",
        {
            "login_form": login_form,
            "register_form": register_form,
            "show_form": "register",
        },
    )


# LOGOUT
def logout_view(request):
    """
    Log the user out and return them to the login screen.
    """
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect("users:login")


# DASHBOARD
@login_required
def dashboard_view(request):
    """
    Show the user a summary of their listings and pledged investments.
    """
    # User-owned listings
    listings = (
        Listing.objects.filter(owner=request.user)
        .prefetch_related("media")
        .order_by("-created_at")
    )

    # User investments
    investments = (
        Investment.objects.filter(investor=request.user, status=Investment.Status.PLEDGED)
        .select_related("listing")
        .prefetch_related("listing__media")
        .order_by("-created_at")
    )

    # Total pledged value
    total_pledged_pence = investments.aggregate(total=Coalesce(Sum("amount_pence"), 0))["total"] or 0
    total_pledged_gbp = (Decimal(total_pledged_pence) / Decimal("100")).quantize(Decimal("0.01"))
    total_pledged_gbp_formatted = f"£{total_pledged_gbp:,.2f}"

    # Dashboard headline figures
    active_investments = investments.values("listing_id").distinct().count()
    active_listings = listings.filter(status=Listing.Status.ACTIVE).count()

    # Draft and awaiting payment listings
    draft_waiting_payment = listings.filter(
        status__in=[Listing.Status.DRAFT, Listing.Status.PENDING_PAYMENT]
    ).count()

    # Render dashboard
    return render(
        request,
        "users/dashboard.html",
        {
            "listings": listings,
            "investments": investments,
            "total_pledged": total_pledged_gbp_formatted,
            "active_investments": active_investments,
            "active_listings": active_listings,
            "draft_waiting_payment": draft_waiting_payment,
        },
    )
