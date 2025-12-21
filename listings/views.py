from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
import logging

import stripe

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from investments.models import Investment

from .forms import ListingCreateForm, ListingMediaForm
from .models import Listing, ListingMedia
from .services.pricing import calculate_listing_price_pence, get_return_pct_range
from .services.payments import (
    reset_payment_state,
    activate_listing_from_paid_session,
    ensure_stripe_configured,
    build_stripe_urls,
    try_reuse_existing_checkout_session,
)

logger = logging.getLogger(__name__)

MAX_IMAGE_SIZE = 5 * 1024 * 1024
MAX_DOCUMENT_SIZE = 10 * 1024 * 1024

ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
ALLOWED_DOCUMENT_EXTENSIONS = {"pdf", "doc", "docx"}

ALLOWED_DOCUMENT_MIME_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

COUNTIES_BY_COUNTRY = {
    "england": ["Greater London", "Kent", "Essex", "Surrey", "Greater Manchester"],
    "scotland": ["Glasgow City", "Edinburgh", "Aberdeenshire"],
    "wales": ["Cardiff", "Swansea", "Gwynedd"],
}

OUTCODES_BY_COUNTY = {
    "Greater London": ["SW", "SE", "N", "E", "W", "NW"],
    "Kent": ["CT", "ME", "TN"],
    "Essex": ["CM", "CO", "IG", "SS"],
    "Surrey": ["GU", "KT", "RH"],
    "Greater Manchester": ["M"],
    "Glasgow City": ["G"],
    "Edinburgh": ["EH"],
    "Aberdeenshire": ["AB"],
    "Cardiff": ["CF"],
    "Swansea": ["SA"],
    "Gwynedd": ["LL"],
}


def validate_uploaded_files(
    files,
    *,
    allowed_exts,
    max_size,
    label,
    allowed_exts_label,
    mime_prefix=None,
    mime_types=None,
):
    for f in files:
        filename = f.name
        ext = filename.rsplit(".", 1)[-1].lower()

        if ext not in allowed_exts:
            raise ValueError(
                f"{label}: {filename} — only {allowed_exts_label} files are allowed."
            )

        if f.size > max_size:
            mb = max_size // (1024 * 1024)
            raise ValueError(f"{label}: {filename} — max size is {mb}MB.")

        content_type = (getattr(f, "content_type", "") or "").lower()

        if mime_prefix and not content_type.startswith(mime_prefix):
            raise ValueError(
                f"{label}: {filename} — only {allowed_exts_label} files are allowed."
            )

        if mime_types and content_type not in mime_types:
            raise ValueError(
                f"{label}: {filename} — only {allowed_exts_label} files are allowed."
            )


def _is_filled(value) -> bool:
    return value is not None and str(value).strip() != ""


def _listing_step_flags(listing: Listing) -> dict:
    """
    Steps:
    1 = Project details (project_name optional; project_duration_days required for completion)
    2 = Project type (source_use + target_use)
    3 = Funding & returns (funding_band + return_type + return_band + duration_days)
    4 = Location (country + county + postcode_prefix)
    5 = Uploads (at least 1 media)
    6 = Activate listing (should be TRUE ONLY when listing is ACTIVE)
    """
    step1 = listing.project_duration_days is not None

    step2 = _is_filled(listing.source_use) and _is_filled(listing.target_use)

    step3 = (
        _is_filled(listing.funding_band)
        and _is_filled(listing.return_type)
        and _is_filled(listing.return_band)
        and (listing.duration_days is not None)
    )

    step4 = (
        _is_filled(listing.country)
        and _is_filled(listing.county)
        and _is_filled(listing.postcode_prefix)
    )

    step5 = listing.media.exists()

    # IMPORTANT: Step 6 means "activated", not "ready".
    step6 = listing.status == Listing.Status.ACTIVE

    return {
        "step1_done": step1,
        "step2_done": step2,
        "step3_done": step3,
        "step4_done": step4,
        "step5_done": step5,
        "step6_done": step6,
    }


def _listing_ready_for_activation(listing: Listing) -> bool:
    """
    Server-side enforcement for activation readiness.
    NOTE: project_name is optional; do NOT require it here.
    """
    required_fields = [
        listing.project_duration_days,
        listing.source_use,
        listing.target_use,
        listing.funding_band,
        listing.return_type,
        listing.return_band,
        listing.duration_days,
        listing.country,
        listing.county,
        listing.postcode_prefix,
    ]

    if any(v in (None, "", []) for v in required_fields):
        return False

    if not listing.media.exists():
        return False

    return True


def _money(x: Decimal) -> str:
    return str(x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


@login_required
def create_listing_view(request):
    """
    Supports two submit actions:
    - action=save_draft  -> saves partial listing (no strict form validation)
    - action=activate    -> requires full validation, saves draft, then proceeds to activation (Stripe checkout)
    """
    if request.method == "POST":
        action = (request.POST.get("action") or "save_draft").strip()

        form = ListingCreateForm(request.POST)
        media_form = ListingMediaForm()

        images = request.FILES.getlist("images")
        documents = request.FILES.getlist("documents")

        try:
            if images:
                validate_uploaded_files(
                    images,
                    allowed_exts=ALLOWED_IMAGE_EXTENSIONS,
                    max_size=MAX_IMAGE_SIZE,
                    mime_prefix="image/",
                    label="Images",
                    allowed_exts_label="JPG, PNG or WEBP",
                )
            if documents:
                validate_uploaded_files(
                    documents,
                    allowed_exts=ALLOWED_DOCUMENT_EXTENSIONS,
                    max_size=MAX_DOCUMENT_SIZE,
                    mime_types=ALLOWED_DOCUMENT_MIME_TYPES,
                    label="Documents",
                    allowed_exts_label="PDF, DOC or DOCX",
                )
        except ValueError as e:
            messages.error(request, str(e))
            return render(
                request,
                "listings/create_listing.html",
                {"form": form, "media_form": media_form},
            )

        if action == "save_draft":
            listing = Listing(owner=request.user, status=Listing.Status.DRAFT)

            for field_name in form.fields.keys():
                if not hasattr(listing, field_name):
                    continue

                raw = (request.POST.get(field_name) or "").strip()

                if raw == "":
                    setattr(listing, field_name, None)
                    continue

                if field_name in {"duration_days", "project_duration_days"}:
                    try:
                        setattr(listing, field_name, int(raw))
                    except Exception:
                        setattr(listing, field_name, None)
                    continue

                setattr(listing, field_name, raw)

            listing.save()

            for image in images:
                ListingMedia.objects.create(
                    listing=listing,
                    file=image,
                    media_type=ListingMedia.MediaType.IMAGE,
                )

            for doc in documents:
                ListingMedia.objects.create(
                    listing=listing,
                    file=doc,
                    media_type=ListingMedia.MediaType.DOCUMENT,
                )

            messages.success(request, "Draft saved. You can edit it anytime from the dashboard.")
            return redirect("users:dashboard")

        if action == "activate":
            if not form.is_valid():
                messages.error(request, "Please complete the required fields before activating.")
                return render(
                    request,
                    "listings/create_listing.html",
                    {"form": form, "media_form": media_form},
                )

            listing = form.save(commit=False)
            listing.owner = request.user
            listing.status = Listing.Status.DRAFT
            reset_payment_state(listing)
            listing.save()

            for image in images:
                ListingMedia.objects.create(
                    listing=listing,
                    file=image,
                    media_type=ListingMedia.MediaType.IMAGE,
                )

            for doc in documents:
                ListingMedia.objects.create(
                    listing=listing,
                    file=doc,
                    media_type=ListingMedia.MediaType.DOCUMENT,
                )

            if not _listing_ready_for_activation(listing):
                messages.error(request, "Complete Steps 1–5 (including at least one upload) before activating.")
                return redirect("listings:listing_edit", pk=listing.pk)

            return redirect("listings:activate_listing", pk=listing.pk)

        messages.error(request, "Unknown action.")
        return render(
            request,
            "listings/create_listing.html",
            {"form": form, "media_form": media_form},
        )

    # GET
    form = ListingCreateForm()
    media_form = ListingMediaForm()
    return render(
        request,
        "listings/create_listing.html",
        {"form": form, "media_form": media_form},
    )


@login_required
def edit_listing_view(request, pk):
    listing = get_object_or_404(
        Listing.objects.prefetch_related("media"),
        pk=pk,
        owner=request.user,
    )

    if listing.status != Listing.Status.DRAFT:
        messages.error(request, "Only draft listings can be edited.")
        return redirect("listings:listing_detail", pk=listing.pk)

    images_qs = listing.media.filter(media_type=ListingMedia.MediaType.IMAGE).order_by("uploaded_at")
    documents_qs = listing.media.filter(media_type=ListingMedia.MediaType.DOCUMENT).order_by("uploaded_at")

    if request.method == "POST":
        action = (request.POST.get("action") or "save_draft").strip()

        form = ListingCreateForm(request.POST, instance=listing)
        media_form = ListingMediaForm()

        images = request.FILES.getlist("images")
        documents = request.FILES.getlist("documents")

        try:
            if images:
                validate_uploaded_files(
                    images,
                    allowed_exts=ALLOWED_IMAGE_EXTENSIONS,
                    max_size=MAX_IMAGE_SIZE,
                    mime_prefix="image/",
                    label="Images",
                    allowed_exts_label="JPG, PNG or WEBP",
                )
            if documents:
                validate_uploaded_files(
                    documents,
                    allowed_exts=ALLOWED_DOCUMENT_EXTENSIONS,
                    max_size=MAX_DOCUMENT_SIZE,
                    mime_types=ALLOWED_DOCUMENT_MIME_TYPES,
                    label="Documents",
                    allowed_exts_label="PDF, DOC or DOCX",
                )
        except ValueError as e:
            messages.error(request, str(e))
            flags = _listing_step_flags(listing)
            return render(
                request,
                "listings/edit_listing.html",
                {
                    "form": form,
                    "media_form": media_form,
                    "listing": listing,
                    "images": images_qs,
                    "documents": documents_qs,
                    **flags,
                },
            )

        if action == "save_draft":
            for field_name in ListingCreateForm.Meta.fields:
                if not hasattr(listing, field_name):
                    continue

                raw = request.POST.get(field_name, "")
                raw = raw.strip() if isinstance(raw, str) else raw

                if raw in ("", None):
                    setattr(listing, field_name, None)
                    continue

                if field_name in {"duration_days", "project_duration_days"}:
                    try:
                        setattr(listing, field_name, int(raw))
                    except Exception:
                        setattr(listing, field_name, None)
                    continue

                setattr(listing, field_name, raw)

            reset_payment_state(listing)
            listing.save()

            for image in images:
                ListingMedia.objects.create(
                    listing=listing,
                    file=image,
                    media_type=ListingMedia.MediaType.IMAGE,
                )
            for doc in documents:
                ListingMedia.objects.create(
                    listing=listing,
                    file=doc,
                    media_type=ListingMedia.MediaType.DOCUMENT,
                )

            messages.success(request, "Draft updated. You can keep editing anytime.")
            return redirect("listings:listing_edit", pk=listing.pk)

        if action == "activate":
            if not form.is_valid():
                messages.error(request, "Please complete the required fields before activating.")
                flags = _listing_step_flags(listing)
                return render(
                    request,
                    "listings/edit_listing.html",
                    {
                        "form": form,
                        "media_form": media_form,
                        "listing": listing,
                        "images": images_qs,
                        "documents": documents_qs,
                        **flags,
                    },
                )

            listing = form.save(commit=False)
            reset_payment_state(listing)
            listing.save()

            for image in images:
                ListingMedia.objects.create(
                    listing=listing,
                    file=image,
                    media_type=ListingMedia.MediaType.IMAGE,
                )
            for doc in documents:
                ListingMedia.objects.create(
                    listing=listing,
                    file=doc,
                    media_type=ListingMedia.MediaType.DOCUMENT,
                )

            if not _listing_ready_for_activation(listing):
                messages.error(request, "Complete Steps 1–5 (including at least one upload) before activating.")
                return redirect("listings:listing_edit", pk=listing.pk)

            return redirect("listings:activate_listing", pk=listing.pk)

        messages.error(request, "Unknown action.")
        return redirect("listings:listing_edit", pk=listing.pk)

    form = ListingCreateForm(instance=listing)
    media_form = ListingMediaForm()
    flags = _listing_step_flags(listing)

    return render(
        request,
        "listings/edit_listing.html",
        {
            "form": form,
            "media_form": media_form,
            "listing": listing,
            "images": images_qs,
            "documents": documents_qs,
            **flags,
        },
    )


@login_required
def listing_detail_view(request, pk):
    listing = get_object_or_404(
        Listing.objects.prefetch_related("media"),
        pk=pk,
        owner=request.user,
    )

    images = listing.media.filter(media_type=ListingMedia.MediaType.IMAGE).order_by("uploaded_at")
    documents = listing.media.filter(media_type=ListingMedia.MediaType.DOCUMENT).order_by("uploaded_at")

    return render(
        request,
        "listings/listing_detail.html",
        {"listing": listing, "images": images, "documents": documents},
    )


@login_required
@require_POST
def listing_delete_view(request, pk):
    listing = get_object_or_404(Listing.objects.prefetch_related("media"), pk=pk, owner=request.user)

    if listing.status != Listing.Status.DRAFT:
        messages.error(request, "Only draft listings can be deleted.")
        return redirect("listings:listing_detail", pk=pk)

    password = (request.POST.get("password") or "").strip()
    if not password or not request.user.check_password(password):
        messages.error(request, "Incorrect password. Listing was not deleted.")
        return redirect("listings:listing_detail", pk=pk)

    for m in listing.media.all():
        try:
            m.file.delete(save=False)
        except Exception:
            pass
    listing.media.all().delete()

    listing.delete()

    messages.success(request, "Listing deleted.")
    return redirect("users:dashboard")


@login_required
@require_POST
def listing_media_delete_view(request, pk, media_id):
    listing = get_object_or_404(Listing, pk=pk, owner=request.user)

    if listing.status != Listing.Status.DRAFT:
        messages.error(request, "Only draft listings can be edited.")
        return redirect("listings:listing_detail", pk=listing.pk)

    media = get_object_or_404(ListingMedia, pk=media_id, listing=listing)

    media.file.delete(save=False)
    media.delete()

    messages.success(request, "File deleted.")
    return redirect("listings:listing_edit", pk=listing.pk)


@login_required
def activate_listing_view(request, pk):
    listing = get_object_or_404(
        Listing.objects.prefetch_related("media"),
        pk=pk,
        owner=request.user,
    )

    if listing.status != Listing.Status.DRAFT:
        messages.error(request, "Only draft listings can be activated.")
        return redirect("listings:listing_detail", pk=listing.pk)

    if not _listing_ready_for_activation(listing):
        messages.error(request, "Complete Steps 1–5 (including at least one upload) before activating.")
        return redirect("listings:listing_edit", pk=listing.pk)

    return start_listing_checkout_view(request, pk=listing.pk)


@login_required
def start_listing_checkout_view(request, pk):
    listing = get_object_or_404(Listing, pk=pk, owner=request.user)

    if listing.status != Listing.Status.DRAFT:
        messages.error(request, "Only draft listings can be paid for.")
        return redirect("listings:listing_detail", pk=listing.pk)

    try:
        ensure_stripe_configured()
    except RuntimeError:
        messages.error(request, "Stripe is not configured on the server.")
        return redirect("listings:listing_detail", pk=listing.pk)

    # Reuse an open checkout session if it exists
    reused_url = try_reuse_existing_checkout_session(listing=listing)
    if reused_url:
        return redirect(reused_url, permanent=False)

    duration_days = int(listing.duration_days)

    try:
        amount_pence = calculate_listing_price_pence(
            funding_band=listing.funding_band,
            duration_days=duration_days,
        )
    except ValueError:
        messages.error(request, "Pricing could not be calculated for this listing.")
        return redirect("listings:listing_detail", pk=listing.pk)

    success_url, cancel_url = build_stripe_urls(listing=listing)

    session = stripe.checkout.Session.create(
        mode="payment",
        currency="gbp",
        client_reference_id=str(listing.pk),
        metadata={
            "listing_id": str(listing.pk),
            "user_id": str(request.user.pk),
            "funding_band": listing.funding_band,
            "duration_days": str(duration_days),
        },
        line_items=[
            {
                "price_data": {
                    "currency": "gbp",
                    "product_data": {"name": "Listing upload fee"},
                    "unit_amount": int(amount_pence),
                },
                "quantity": 1,
            }
        ],
        success_url=success_url,
        cancel_url=cancel_url,
    )

    listing.expected_amount_pence = int(amount_pence)
    listing.stripe_checkout_session_id = session.id
    listing.save(update_fields=["expected_amount_pence", "stripe_checkout_session_id"])

    return redirect(session.url, permanent=False)


@login_required
def payment_success_view(request):
    listing_id = (request.GET.get("listing_id") or "").strip()
    session_id = (request.GET.get("session_id") or "").strip()

    if not (listing_id and session_id and settings.STRIPE_SECRET_KEY):
        messages.success(request, "Payment received. Your listing will activate shortly.")
        return redirect("users:dashboard")

    stripe.api_key = settings.STRIPE_SECRET_KEY

    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except stripe.error.StripeError:
        messages.success(request, "Payment received. Your listing will activate shortly.")
        return redirect("users:dashboard")

    try:
        with transaction.atomic():
            listing = Listing.objects.select_for_update().get(pk=listing_id, owner=request.user)
            activated = activate_listing_from_paid_session(listing=listing, session=session)
    except Listing.DoesNotExist:
        activated = False

    if activated:
        messages.success(request, "Payment received. Your listing is now active.")
    else:
        messages.success(request, "Payment received. Your listing will activate shortly.")

    return redirect("users:dashboard")


@login_required
def payment_cancel_view(request, pk):
    listing = get_object_or_404(Listing, pk=pk, owner=request.user)

    reset_payment_state(listing)
    listing.save(
        update_fields=[
            "status",
            "expected_amount_pence",
            "paid_amount_pence",
            "paid_at",
            "stripe_checkout_session_id",
            "stripe_payment_intent_id",
        ]
    )

    messages.info(request, "Payment cancelled. Your listing is still saved as a draft.")
    return redirect("listings:listing_detail", pk=pk)


@csrf_exempt
@require_POST
def stripe_webhook(request):
    if not settings.STRIPE_WEBHOOK_SECRET or not settings.STRIPE_SECRET_KEY:
        return HttpResponse(status=400)

    stripe.api_key = settings.STRIPE_SECRET_KEY

    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=settings.STRIPE_WEBHOOK_SECRET,
        )
    except Exception:
        return HttpResponse(status=400)

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]

        if session.get("payment_status") != "paid":
            return HttpResponse(status=200)

        listing_id = session.get("client_reference_id") or (session.get("metadata") or {}).get("listing_id")
        if not listing_id:
            return HttpResponse(status=200)

        session_id = session.get("id")

        with transaction.atomic():
            listing = Listing.objects.select_for_update().filter(pk=listing_id).first()
            if not listing:
                return HttpResponse(status=200)

            if listing.status == Listing.Status.ACTIVE:
                return HttpResponse(status=200)

            if listing.stripe_checkout_session_id and session_id != listing.stripe_checkout_session_id:
                return HttpResponse(status=200)

            activate_listing_from_paid_session(listing=listing, session=session)

    return HttpResponse(status=200)


@login_required
@require_GET
def api_counties(request):
    country = (request.GET.get("country") or "").strip().lower()
    return JsonResponse({"counties": COUNTIES_BY_COUNTRY.get(country, [])})


@login_required
@require_GET
def api_outcodes(request):
    county = (request.GET.get("county") or "").strip()
    return JsonResponse({"outcodes": OUTCODES_BY_COUNTY.get(county, [])})


@login_required
def search_listings_view(request):
    q = (request.GET.get("q") or "").strip()
    country = (request.GET.get("country") or "").strip().lower()
    county = (request.GET.get("county") or "").strip()
    postcode_prefix = (request.GET.get("postcode_prefix") or "").strip()
    funding_band = (request.GET.get("funding_band") or "").strip()
    return_type = (request.GET.get("return_type") or "").strip()

    qs = (
        Listing.objects.filter(status=Listing.Status.ACTIVE)
        .exclude(owner=request.user)
        .prefetch_related("media")
        .order_by("-created_at")
    )

    if q:
        qs = qs.filter(
            Q(country__icontains=q)
            | Q(county__icontains=q)
            | Q(postcode_prefix__icontains=q)
            | Q(source_use__icontains=q)
            | Q(target_use__icontains=q)
        )

    if country:
        qs = qs.filter(country__iexact=country)

    if county:
        qs = qs.filter(county__iexact=county)

    if postcode_prefix:
        qs = qs.filter(postcode_prefix__iexact=postcode_prefix)

    if funding_band:
        qs = qs.filter(funding_band=funding_band)

    if return_type:
        qs = qs.filter(return_type=return_type)

    paginator = Paginator(qs, 12)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "listings/search_listings.html",
        {
            "q": q,
            "country": country,
            "county": county,
            "postcode_prefix": postcode_prefix,
            "funding_band": funding_band,
            "return_type": return_type,
            "page_obj": page_obj,
            "funding_band_choices": Listing.FundingBand.choices,
            "return_type_choices": Listing.ReturnType.choices,
            "country_choices": Listing.Country.choices,
        },
    )


@login_required
def opportunity_detail_view(request, pk):
    listing = get_object_or_404(
        Listing.objects.prefetch_related("media"),
        pk=pk,
        status=Listing.Status.ACTIVE,
    )

    images = listing.media.filter(media_type=ListingMedia.MediaType.IMAGE).order_by("uploaded_at")
    documents = listing.media.filter(media_type=ListingMedia.MediaType.DOCUMENT).order_by("uploaded_at")

    pledged_pence = (
        Investment.objects.filter(
            listing=listing,
            status=Investment.Status.PLEDGED,
        ).aggregate(total=Coalesce(Sum("amount_pence"), 0))["total"]
        or 0
    )

    pledged_gbp = (Decimal(pledged_pence) / Decimal("100")).quantize(Decimal("0.01"))

    target_gbp = None
    remaining_gbp = None
    progress_pct = 0

    # funding_band format: "10000_20000" (we use upper bound as "target")
    try:
        if listing.funding_band:
            parts = str(listing.funding_band).split("_")
            if len(parts) >= 2:
                target_int = int(parts[-1])
                target_gbp = Decimal(target_int).quantize(Decimal("0.01"))

                remaining = Decimal(target_int) - pledged_gbp
                if remaining < 0:
                    remaining = Decimal("0")
                remaining_gbp = remaining.quantize(Decimal("0.01"))

                if target_int > 0:
                    pct = (pledged_gbp / Decimal(target_int)) * Decimal("100")
                    if pct < 0:
                        pct = Decimal("0")
                    if pct > 100:
                        pct = Decimal("100")
                    progress_pct = int(pct)
    except Exception:
        target_gbp = None
        remaining_gbp = None
        progress_pct = 0

    return render(
        request,
        "listings/opportunity_detail.html",
        {
            "listing": listing,
            "images": images,
            "documents": documents,
            "pledged_gbp": pledged_gbp,
            "target_gbp": target_gbp,
            "remaining_gbp": remaining_gbp,
            "progress_pct": progress_pct,
        },
    )


@require_GET
@login_required
def estimate_return_view(request, pk):
    listing = get_object_or_404(Listing, pk=pk, status=Listing.Status.ACTIVE)

    raw = (request.GET.get("amount") or "").strip()
    try:
        amount = Decimal(raw)
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid amount."}, status=400)

    if amount <= 0:
        return JsonResponse({"ok": False, "error": "Amount must be greater than 0."}, status=400)

    try:
        min_pct, max_pct = get_return_pct_range(listing)
    except Exception:
        return JsonResponse({"ok": False, "error": "Return band is not configured correctly."}, status=400)

    profit_min = amount * (min_pct / Decimal("100"))
    profit_max = amount * (max_pct / Decimal("100"))

    total_min = amount + profit_min
    total_max = amount + profit_max

    return JsonResponse(
        {
            "ok": True,
            "min_pct": str(min_pct),
            "max_pct": str(max_pct),
            "profit_min": _money(profit_min),
            "profit_max": _money(profit_max),
            "total_min": _money(total_min),
            "total_max": _money(total_max),
            "duration_days": int(listing.duration_days),
            "return_type": listing.get_return_type_display(),
        }
    )
