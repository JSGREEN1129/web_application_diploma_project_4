from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from users.models import Listing
from .forms import InvestmentPledgeForm
from .models import Investment
from .services import calculate_expected_return_pence


def get_listing_apr_percent(listing: Listing) -> float:
    """
    IMPORTANT: Update this to match YOUR Listing model.

    Option A (best): listing has a numeric field like listing.apr_percent
      return float(listing.apr_percent)

    Option B: listing.return_band is a choice like "8" or "8-10"
      parse to a single number (e.g. midpoint or lower bound).
    """
    if hasattr(listing, "apr_percent") and listing.apr_percent is not None:
        return float(listing.apr_percent)

    display = ""
    try:
        display = listing.get_return_band_display()
    except Exception:
        display = str(getattr(listing, "return_band", "") or "")

    display = display.replace("%", "").strip()

    if "-" in display:
        left, right = display.split("-", 1)
        try:
            return (float(left.strip()) + float(right.strip())) / 2.0
        except Exception:
            return 0.0

    try:
        return float(display)
    except Exception:
        return 0.0


@require_POST
@login_required
def pledge_investment_view(request, listing_id: int):
    listing = get_object_or_404(Listing, pk=listing_id, status=Listing.Status.ACTIVE)

    if listing.owner_id == request.user.id:
        messages.error(request, "You cannot invest in your own listing.")
        return redirect("users:search_listings")

    form = InvestmentPledgeForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Enter a valid amount.")
        return redirect("users:search_listings")

    amount_gbp = form.cleaned_data["amount_gbp"]
    amount_pence = int(amount_gbp * 100)

    apr_percent = get_listing_apr_percent(listing)
    if apr_percent <= 0:
        messages.error(request, "This listing does not have a valid return rate configured.")
        return redirect("users:search_listings")

    with transaction.atomic():
        listing = Listing.objects.select_for_update().get(pk=listing.pk)
        if listing.status != Listing.Status.ACTIVE:
            messages.error(request, "This listing is no longer available.")
            return redirect("users:search_listings")

        result = calculate_expected_return_pence(
            amount_pence=amount_pence,
            apr_percent=apr_percent,
            duration_days=int(listing.duration_days),
        )

        Investment.objects.create(
            investor=request.user,
            listing=listing,
            amount_pence=amount_pence,
            expected_return_pence=result.expected_return_pence,
            expected_total_back_pence=result.expected_total_back_pence,
        )

    messages.success(request, "Pledge created.")
    return redirect("users:dashboard")
