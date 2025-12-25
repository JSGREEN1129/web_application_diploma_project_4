from decimal import Decimal, ROUND_HALF_UP

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from listings.models import Listing, ListingMedia
from listings.services.pricing import get_return_pct_range
from .forms import InvestmentPledgeForm
from .models import Investment


def _gbp_to_pence(gbp: Decimal) -> int:
    return int((gbp * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _calc_expected_total_return(amount_pence: int, pct: Decimal) -> tuple[int, int]:
    """
    Treat pct as TOTAL return percent for the opportunity (NOT annualised, NOT pro-rated).
    Returns (expected_return_pence, expected_total_back_pence).
    """
    expected_return = (Decimal(amount_pence) * (pct / Decimal("100"))).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    )
    expected_return_pence = int(expected_return)
    expected_total_back_pence = amount_pence + expected_return_pence
    return expected_return_pence, expected_total_back_pence


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

    amount_gbp: Decimal = form.cleaned_data["amount_gbp"]
    if amount_gbp <= 0:
        messages.error(request, "Enter a valid amount.")
        return redirect("users:search_listings")

    amount_pence = _gbp_to_pence(amount_gbp)

    try:
        min_pct, max_pct = get_return_pct_range(listing)
    except Exception:
        messages.error(request, "This listing does not have a valid return band configured.")
        return redirect("users:search_listings")

    mid_pct = (min_pct + max_pct) / Decimal("2")

    with transaction.atomic():
        listing = Listing.objects.select_for_update().get(pk=listing.pk)
        if listing.status != Listing.Status.ACTIVE:
            messages.error(request, "This listing is no longer available.")
            return redirect("users:search_listings")

        now = timezone.now()
        if listing.active_until and listing.active_until <= now:
            messages.error(request, "This listing has expired.")
            return redirect("users:search_listings")

        expected_return_pence, expected_total_back_pence = _calc_expected_total_return(
            amount_pence=amount_pence,
            pct=mid_pct,
        )

        investment = Investment.objects.create(
            investor=request.user,
            listing=listing,
            amount_pence=amount_pence,
            expected_return_pence=expected_return_pence,
            expected_total_back_pence=expected_total_back_pence,
            status=Investment.Status.PLEDGED,
        )

    messages.success(
        request, 
        f"Pledge created. Pledged Amount: £{investment.amount_gbp:,.2f}, Est. Return: £{investment.expected_return_gbp:,.2f}, Est. Total Back: £{investment.expected_total_back_gbp:,.2f}"
    )
    return redirect("users:dashboard")


@require_POST
@login_required
def retract_pledge_view(request, investment_id: int):
    """
    Retract (cancel) a pledge only if:
      - it belongs to the logged-in user
      - it is currently PLEDGED
      - the related listing is still ACTIVE
      - and (if active_until is set) the listing has not expired yet
    """
    investment = get_object_or_404(
        Investment.objects.select_related("listing"),
        pk=investment_id,
        investor=request.user,
    )

    if investment.status != Investment.Status.PLEDGED:
        messages.error(request, "This pledge cannot be retracted.")
        return redirect("users:dashboard")

    listing = investment.listing
    now = timezone.now()

    if listing.status != Listing.Status.ACTIVE:
        messages.error(request, "You can only retract a pledge while the listing is still active.")
        return redirect("users:dashboard")

    if listing.active_until and listing.active_until <= now:
        messages.error(request, "You can only retract a pledge before the listing expires.")
        return redirect("users:dashboard")

    investment.status = Investment.Status.CANCELLED
    investment.save(update_fields=["status"])

    messages.success(request, "Pledge retracted.")
    return redirect("users:dashboard")
