from datetime import timedelta
import logging

import stripe
from django.conf import settings
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from ..models import Listing

logger = logging.getLogger(__name__)

def reset_payment_state(listing: Listing) -> None:
    listing.status = Listing.Status.DRAFT
    listing.expected_amount_pence = 0
    listing.paid_amount_pence = 0
    listing.paid_at = None
    listing.stripe_checkout_session_id = ""
    listing.stripe_payment_intent_id = ""

def activate_listing_from_paid_session(*, listing: Listing, session: dict) -> bool:
    session_id = session.get("id")
    amount_total = session.get("amount_total")
    payment_intent = session.get("payment_intent")

    # Check if payment is successful
    if session.get("payment_status") != "paid":
        return False

    if not session_id:
        return False

    if listing.status == Listing.Status.ACTIVE:
        return True

    # Ensure the session ID matches
    if listing.stripe_checkout_session_id and session_id != listing.stripe_checkout_session_id:
        return False

    if amount_total is None:
        return False

    # Check if the amount paid matches the expected amount
    if int(amount_total) != int(listing.expected_amount_pence):
        return False

    # Ensure that duration_days is not None before proceeding with activation
    if listing.duration_days is None:
        raise ValueError("Listing duration is required to activate the listing.")
    
    now = timezone.now()
    listing.paid_amount_pence = int(amount_total)
    listing.paid_at = now
    listing.stripe_payment_intent_id = str(payment_intent or "")
    listing.status = Listing.Status.ACTIVE

    # Safely convert duration_days to integer
    duration_days = int(listing.duration_days)
    listing.active_from = now
    listing.active_until = now + timedelta(days=duration_days)

    listing.save(
        update_fields=[
            "paid_amount_pence",
            "paid_at",
            "stripe_payment_intent_id",
            "status",
            "active_from",
            "active_until",
        ]
    )
    return True

def build_stripe_urls(*, listing: Listing) -> tuple[str, str]:
    # Construct the success and cancel URLs for Stripe
    success_url = (
        settings.SITE_URL
        + reverse("listings:payment_success")
        + f"?listing_id={listing.pk}&session_id={{CHECKOUT_SESSION_ID}}"
    )
    cancel_url = settings.SITE_URL + reverse("listings:payment_cancel", kwargs={"pk": listing.pk})
    return success_url, cancel_url

def ensure_stripe_configured() -> None:
    # Ensure Stripe is properly configured
    if not settings.STRIPE_SECRET_KEY:
        raise RuntimeError("Stripe is not configured on the server.")
    stripe.api_key = settings.STRIPE_SECRET_KEY

def try_reuse_existing_checkout_session(*, listing: Listing) -> str | None:
    """
    If a checkout session exists and is still open, return its URL.
    If it is complete, attempt activation and return None.
    """
    if not listing.stripe_checkout_session_id:
        return None

    try:
        existing = stripe.checkout.Session.retrieve(listing.stripe_checkout_session_id)
        existing_status = getattr(existing, "status", None)

        if existing_status == "open" and getattr(existing, "url", None):
            return existing.url

        if existing_status == "complete":
            try:
                paid_session = stripe.checkout.Session.retrieve(listing.stripe_checkout_session_id)
            except stripe.error.StripeError:
                paid_session = None

            if paid_session:
                with transaction.atomic():
                    locked = Listing.objects.select_for_update().get(pk=listing.pk)
                    activate_listing_from_paid_session(listing=locked, session=paid_session)

    except stripe.error.StripeError as e:
        logger.warning(
            "Failed to retrieve checkout session %s for listing %s: %s",
            listing.stripe_checkout_session_id,
            listing.pk,
            str(e),
        )

    return None
