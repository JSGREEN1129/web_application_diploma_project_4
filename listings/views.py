from __future__ import annotations  # Allows forward refs in type hints

from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
import logging

# Stripe SDK used for checkout and webhook verification
import stripe

from django.conf import settings
# Django messages framework
from django.contrib import messages
from django.contrib.auth.decorators import login_required
# Pagination for search results
from django.core.paginator import Paginator
from django.db import transaction, models
from django.db.models import Q, Sum
# Safer SUM default (0) when no rows
from django.db.models.functions import Coalesce
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
# Stripe webhook is CSRF-exempt
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
# Used for pledge progress aggregation
from investments.models import Investment
# Draft form and multi-upload form
from .forms import ListingCreateForm, ListingMediaForm
from .models import Listing, ListingMedia
# Fee pricing and return band %
from .services.pricing import (
    calculate_listing_price_pence,
    get_return_pct_range
)
from .services.payments import (
    # Clears payment fields and status back to DRAFT
    reset_payment_state,
    # Activates listing once Stripe confirms paid
    activate_listing_from_paid_session,
    # Guards missing Stripe secrets
    ensure_stripe_configured,
    # Builds success/cancel URLs with query params
    build_stripe_urls,
    # Avoids creating new sessions unnecessarily
    try_reuse_existing_checkout_session,
)
# Module logger (handy for debugging in production)
logger = logging.getLogger(__name__)

# --- Upload validation limits ---
MAX_IMAGE_SIZE = 5 * 1024 * 1024          # 5MB per image
MAX_DOCUMENT_SIZE = 10 * 1024 * 1024      # 10MB per document

# Allowed image suffixes
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
# Allowed document suffixes
ALLOWED_DOCUMENT_EXTENSIONS = {"pdf", "doc", "docx"}

ALLOWED_DOCUMENT_MIME_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

# --- Simple static location data used by JS dropdown APIs ---
COUNTIES_BY_COUNTRY = {
    "england": ["Greater London", "Kent", "Essex",
                "Surrey", "Greater Manchester"],
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


def _parse_target_int_from_funding_band(funding_band) -> int:
    """
    Listing.FundingBand values look like "10000_20000" (low_high).
    This returns the HIGH end as the target amount in GBP.
    """
    # Used by pledge progress bars: target = high end of band
    if not funding_band:
        return 0
    try:
        # keep low unused; high is the target
        low_str, high_str = str(funding_band).split("_", 1)
        return int(high_str)
    except Exception:
        return 0


def _pledge_progress_for_listing(listing: Listing) -> dict:
    """
    Computes pledged/remaining/target/progress for a single listing.
    Returned keys are safe and always present.
    """
    # Total pledged amount aggregated in pence to avoid float issues
    pledged_pence = (
        Investment.objects.filter(
            listing=listing,
            status=Investment.Status.PLEDGED,
        ).aggregate(total=Coalesce(Sum("amount_pence"), 0))["total"]
        or 0
    )

    # Convert to GBP display string used in templates
    pledged_gbp = (
        Decimal(pledged_pence) / Decimal("100")
        ).quantize(Decimal("0.01"))
    pledged_gbp_formatted = f"£{pledged_gbp:,.2f}"

    # Funding target derived from funding band
    target_int = _parse_target_int_from_funding_band(listing.funding_band)

    # Defaults
    target_gbp_formatted = None
    remaining_gbp_formatted = None
    progress_pct = 0

    if target_int > 0:
        target_gbp = Decimal(target_int).quantize(Decimal("0.01"))
        target_gbp_formatted = f"{target_gbp:,.2f}"

        remaining = Decimal(target_int) - pledged_gbp
        if remaining < 0:
            remaining = Decimal("0")
        remaining_gbp = remaining.quantize(Decimal("0.01"))
        remaining_gbp_formatted = f"£{remaining_gbp:,.2f}"

        # Clamp progress to [0, 100] for safe progress bar rendering
        pct = (pledged_gbp / Decimal(target_int)) * Decimal("100")
        if pct < 0:
            pct = Decimal("0")
        if pct > 100:
            pct = Decimal("100")
        progress_pct = int(pct)

    return {
        "pledged_gbp": pledged_gbp_formatted,
        "target_gbp": target_gbp_formatted,
        "remaining_gbp": remaining_gbp_formatted,
        "progress_pct": progress_pct,
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
    # Shared validator for images and documents
    for f in files:
        filename = f.name
        ext = filename.rsplit(".", 1)[-1].lower()

        # Extension validation
        if ext not in allowed_exts:
            raise ValueError(
                f"{label}: {filename} — "
                f"only {allowed_exts_label} files are allowed."
            )

        # Size validation
        if f.size > max_size:
            mb = max_size // (1024 * 1024)
            raise ValueError(f"{label}: {filename} — max size is {mb}MB.")

        # MIME validation
        content_type = (getattr(f, "content_type", "") or "").lower()

        if mime_prefix and not content_type.startswith(mime_prefix):
            raise ValueError(
                f"{label}: {filename} — only "
                f"{allowed_exts_label} files are allowed."
            )

        if mime_types and content_type not in mime_types:
            raise ValueError(
                f"{label}: {filename} — only "
                f"{allowed_exts_label} files are allowed."
            )


def _is_filled(value) -> bool:
    # Normalise "filled" definition across payload and model objects
    return value is not None and str(value).strip() != ""


def _step_flags_from_payload(
    payload: dict,
    *,
    has_media: bool,
    is_active: bool,
) -> dict:
    """
    Compute step flags from raw POST-like payload.
    This is what you use to update steppers *without saving*.

    Step rules match _listing_step_flags:
      1: project_duration_days required
      2: source_use + target_use
      3: funding_band + return_type + return_band + duration_days
      4: country + county + postcode_prefix
      5: has_media
      6: is_active (activated)
    """
    # Pull raw values directly from request.POST-style dict
    project_duration_days = payload.get("project_duration_days")
    source_use = payload.get("source_use")
    target_use = payload.get("target_use")
    funding_band = payload.get("funding_band")
    return_type = payload.get("return_type")
    return_band = payload.get("return_band")
    duration_days = payload.get("duration_days")
    country = payload.get("country")
    county = payload.get("county")
    postcode_prefix = payload.get("postcode_prefix")

    # Step completion checks
    step1 = _is_filled(project_duration_days)
    step2 = _is_filled(source_use) and _is_filled(target_use)
    step3 = (
        _is_filled(funding_band)
        and _is_filled(return_type)
        and _is_filled(return_band)
        and _is_filled(duration_days)
    )
    step4 = (
        _is_filled(country)
        and _is_filled(county)
        and _is_filled(postcode_prefix)
    )
    step5 = bool(has_media)
    step6 = bool(is_active)

    # Activation should only show as available BEFORE activation
    can_activate = (
        step1
        and step2
        and step3
        and step4
        and step5
        and (not step6)
    )
    return {
        "step1_done": step1,
        "step2_done": step2,
        "step3_done": step3,
        "step4_done": step4,
        "step5_done": step5,
        "step6_done": step6,
        "can_activate": can_activate,
    }


def _listing_step_flags(listing: Listing) -> dict:
    """
    Server truth for saved listings (Edit page uses this).
    """
    # Mirrors _step_flags_from_payload but uses persisted listing values
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
    step5 = listing.media.exists()  # DB truth: at least one upload
    step6 = listing.status == Listing.Status.ACTIVE
    can_activate = step1 and step2 and step3 and step4 and step5 and not step6

    return {
        "step1_done": step1,
        "step2_done": step2,
        "step3_done": step3,
        "step4_done": step4,
        "step5_done": step5,
        "step6_done": step6,
        "can_activate": can_activate,
    }


def _listing_ready_for_activation(listing: Listing) -> bool:
    # Final pre-activation gate used by create/edit/activate flows
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

    # Reject missing and empty values
    if any(v in (None, "", []) for v in required_fields):
        return False

    # Require at least one uploaded file to activate
    if not listing.media.exists():
        return False

    return True


def _money(x: Decimal) -> str:
    # Formats a Decimal to "0.01" precision as a string
    return str(x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _assign_field_from_raw(listing: Listing, field_name: str, raw) -> None:
    """
    Draft-safe assignment:
    - Empty -> None OR "" depending on
    DB nullability (prevents NOT NULL crashes)
    - duration_days/project_duration_days -> int coercion
    - everything else -> raw string
    """
    # Used for save_draft actions where partial forms are allowed
    if not hasattr(listing, field_name):
        return

    model_field = Listing._meta.get_field(field_name)

    if raw is None:
        raw = ""
    if isinstance(raw, str):
        raw = raw.strip()

    if raw == "":
        # If a CharField has null=False, never assign None.
        if isinstance(model_field, models.CharField) and not model_field.null:
            setattr(listing, field_name, "")
        else:
            setattr(listing, field_name, None)
        return

    # Coerce the duration fields to ints
    if field_name in {"duration_days", "project_duration_days"}:
        try:
            setattr(listing, field_name, int(raw))
        except Exception:
            setattr(listing, field_name, None)
        return

    # Everything else: store as raw value
    setattr(listing, field_name, raw)


@login_required
@require_POST
def api_listing_stepper_flags(request, pk=None):
    """
    Returns JSON step flags based on *current form values* without saving.
    This is what lets create/edit
    steppers update WITHOUT submitting the full form.

    - For create: call this with no pk (or pk=None route)
    - For edit: call this with pk so existing media can count towards Step 5

    For Step 5 (uploads), the client should send:
      media_selected = "1" if there are
      any file inputs selected in the browser.

    This avoids trying to transmit files just to compute the stepper.
    """
    listing = None
    existing_has_media = False
    is_active = False

    # If pk is provided, we compute Step 5 based on existing media too
    if pk is not None:
        listing = get_object_or_404(
            Listing.objects.prefetch_related("media"),
            pk=pk,
            owner=request.user,
        )
        existing_has_media = listing.media.exists()
        is_active = listing.status == Listing.Status.ACTIVE

    # Client-side hint for Step 5
    media_selected = (request.POST.get("media_selected") or "").strip()
    client_has_media = media_selected in {"1", "true", "True", "yes", "on"}

    flags = _step_flags_from_payload(
        request.POST,
        has_media=(existing_has_media or client_has_media),
        is_active=is_active,
    )

    # Human-friendly stepper message used by create and edit templates
    if flags["can_activate"]:
        msg = "Steps 1–5 complete — activation is available."
        msg_class = "text-success"
    else:
        if not (
            flags["step1_done"]
            and flags["step2_done"]
            and flags["step3_done"]
            and flags["step4_done"]
        ):
            msg = "Complete steps 1–4 to enable activation. "
            "You can save a draft at any time."
        elif not flags["step5_done"]:
            msg = "Upload at least one image or document to complete Step 5."
        else:
            msg = "Complete steps 1–5 to enable activation."
        msg_class = "text-muted"

    return JsonResponse(
        {
            "ok": True,
            **flags,
            "msg": msg,
            "msg_class": msg_class,
        }
    )


@login_required
def create_listing_view(request):
    """
    Supports two submit actions:
    - action=save_draft  -> saves partial listing (no strict form validation)
    - action=activate    -> requires full validation, saves draft,
    then proceeds to activation (Stripe checkout)

    NOTE:
    This view supplies step flags to the template
    (like edit_listing_view does),
    so both pages can use the same stepper logic.
    """
    if request.method == "POST":
        # Button-controlled action
        action = (request.POST.get("action") or "save_draft").strip()
        # Full form (only strictly enforced for activate)
        form = ListingCreateForm(request.POST)
        media_form = ListingMediaForm()         # Upload form (multi-inputs)
        # Multi-upload images
        images = request.FILES.getlist("images")
        # Multi-upload documents
        documents = request.FILES.getlist("documents")

        # Stepper flags computed from current POST values
        flags = _step_flags_from_payload(
            request.POST,
            has_media=bool(images or documents),
            is_active=False,
        )

        # Validate files up-front so draft saving
        # doesn't accept disallowed files
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
            # File validation errors are shown via
            # messages framework and template alert
            messages.error(request, str(e))
            return render(
                request,
                "listings/create_listing.html",
                {
                    "form": form,
                    "media_form": media_form,
                    # Preserve dropdown state even if form didn't validate
                    "posted_country": (
                        request.POST.get("country") or ""
                        ).strip(),
                    "posted_county": (
                        request.POST.get("county") or ""
                        ).strip(),
                    "posted_outcode": (
                        request.POST.get("postcode_prefix") or ""
                        ).strip(),
                    **flags,
                },
            )

        if action == "save_draft":
            # Draft save allows partial fields without full form validation
            listing = Listing(owner=request.user, status=Listing.Status.DRAFT)

            for field_name in form.fields.keys():
                raw = request.POST.get(field_name)
                _assign_field_from_raw(listing, field_name, raw)

            listing.save()

            # Persist uploads to ListingMedia table
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

            messages.success(
                request,
                "Draft saved. You can edit it anytime from the dashboard.",
            )
            return redirect("users:dashboard")

        if action == "activate":
            # Activation requires form validity
            if not form.is_valid():
                messages.error(
                    request, "Please complete the "
                    "required fields before activating."
                )
                return render(
                    request,
                    "listings/create_listing.html",
                    {"form": form, "media_form": media_form, **flags},
                )

            # Save listing first as DRAFT and reset payment state
            listing = form.save(commit=False)
            listing.owner = request.user
            listing.status = Listing.Status.DRAFT
            reset_payment_state(listing)
            listing.save()

            # Save uploads before activation readiness check
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

            # Enforce Steps 1–5 complete
            if not _listing_ready_for_activation(listing):
                messages.error(
                    request,
                    "Complete Steps 1–5 (including at least one upload) "
                    "before activating.",
                )
                return redirect("listings:edit_listing", pk=listing.pk)

            # Activation flow then redirects into checkout
            return redirect("listings:activate_listing", pk=listing.pk)

        # Unknown action fallback
        messages.error(request, "Unknown action.")
        return render(
            request,
            "listings/create_listing.html",
            {"form": form, "media_form": media_form, **flags},
        )

    # GET: blank create form + default stepper flags
    form = ListingCreateForm()
    media_form = ListingMediaForm()
    flags = _step_flags_from_payload({}, has_media=False, is_active=False)

    return render(
        request,
        "listings/create_listing.html",
        {"form": form, "media_form": media_form, **flags},
    )


@login_required
def edit_listing_view(request, pk):
    # Owner-only edit page for drafts
    listing = get_object_or_404(
        Listing.objects.prefetch_related("media"),
        pk=pk,
        owner=request.user,
    )

    # Hard gate: only drafts editable
    if listing.status != Listing.Status.DRAFT:
        messages.error(request, "Only draft listings can be edited.")
        return redirect("listings:listing_detail", pk=listing.pk)

    # Existing uploads split by type for UI tabs and counts
    images_qs = listing.media.filter(
        media_type=ListingMedia.MediaType.IMAGE
    ).order_by("uploaded_at")
    documents_qs = listing.media.filter(
        media_type=ListingMedia.MediaType.DOCUMENT
    ).order_by("uploaded_at")

    if request.method == "POST":
        action = (request.POST.get("action") or "save_draft").strip()
        # Bound to instance for activate flow
        form = ListingCreateForm(request.POST, instance=listing)
        media_form = ListingMediaForm()

        images = request.FILES.getlist("images")
        documents = request.FILES.getlist("documents")

        # Validate uploaded files before saving updates
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
            # On validation error,
            # re-render edit page with existing media preserved
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
            # Partial-save logic:
            # use raw POST assignment rather than strict form validation
            for field_name in ListingCreateForm.Meta.fields:
                raw = request.POST.get(field_name)
                _assign_field_from_raw(listing, field_name, raw)

            # Reset payment fields if any draft fields changed
            reset_payment_state(listing)
            listing.save()

            # Append new uploads if present
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

            messages.success(request,
                             "Draft updated. You can keep editing anytime.")
            return redirect("listings:edit_listing", pk=listing.pk)

        if action == "activate":
            # Activation requires full form validation
            if not form.is_valid():
                messages.error(
                    request, "Please complete the "
                    "required fields before activating."
                )
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

            # Save validated fields and reset payment state before checkout
            listing = form.save(commit=False)
            reset_payment_state(listing)
            listing.save()

            # Save any newly uploaded files
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

            # Must meet Steps 1–5 before activation
            if not _listing_ready_for_activation(listing):
                messages.error(
                    request,
                    "Complete Steps 1–5 (including at least one upload) "
                    "before activating.",
                )
                return redirect("listings:edit_listing", pk=listing.pk)

            return redirect("listings:activate_listing", pk=listing.pk)

        # Unknown action fallback
        messages.error(request, "Unknown action.")
        return redirect("listings:edit_listing", pk=listing.pk)

    # GET: populate edit form and stepper flags based on saved listing
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
    # Owner-only listing detail page (shows uploads and pledge progress)
    listing = get_object_or_404(
        Listing.objects.prefetch_related("media"),
        pk=pk,
        owner=request.user,
    )

    images = listing.media.filter(
        media_type=ListingMedia.MediaType.IMAGE
    ).order_by("uploaded_at")
    documents = listing.media.filter(
        media_type=ListingMedia.MediaType.DOCUMENT
    ).order_by("uploaded_at")
    # Provides pledged/remaining/target/progress_pct
    pledge_ctx = _pledge_progress_for_listing(listing)

    return render(
        request,
        "listings/listing_detail.html",
        {
            "listing": listing,
            "images": images,
            "documents": documents,
            **pledge_ctx,
        },
    )


@login_required
@require_POST
def listing_delete_view(request, pk):
    # Draft-only delete, owner-only, password-confirmed
    listing = get_object_or_404(
        Listing.objects.prefetch_related("media"),
        pk=pk,
        owner=request.user,
    )

    if listing.status != Listing.Status.DRAFT:
        messages.error(request, "Only draft listings can be deleted.")
        return redirect("listings:listing_detail", pk=pk)

    password = (request.POST.get("password") or "").strip()
    if not password or not request.user.check_password(password):
        messages.error(request, "Incorrect password. Listing was not deleted.")
        return redirect("listings:listing_detail", pk=pk)

    # Delete backing files first, then delete DB rows
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
    # Owner deletes a single uploaded file
    listing = get_object_or_404(Listing, pk=pk, owner=request.user)

    if listing.status != Listing.Status.DRAFT:
        messages.error(request, "Only draft listings can be edited.")
        return redirect("listings:listing_detail", pk=listing.pk)

    media = get_object_or_404(ListingMedia, pk=media_id, listing=listing)

    media.file.delete(save=False)  # Remove physical file
    media.delete()                 # Remove DB row

    messages.success(request, "File deleted.")
    return redirect("listings:edit_listing", pk=listing.pk)


@login_required
def activate_listing_view(request, pk):
    # Activation entry point — redirects into checkout
    listing = get_object_or_404(
        Listing.objects.prefetch_related("media"),
        pk=pk,
        owner=request.user,
    )

    if listing.status != Listing.Status.DRAFT:
        messages.error(request, "Only draft listings can be activated.")
        return redirect("listings:listing_detail", pk=listing.pk)

    if not _listing_ready_for_activation(listing):
        messages.error(
            request, "Complete Steps 1–5 "
            "(including at least one upload) before activating."
        )
        return redirect("listings:edit_listing", pk=listing.pk)
    # Delegates to Stripe checkout creator
    return start_listing_checkout_view(request, pk=listing.pk)


@login_required
def start_listing_checkout_view(request, pk):
    # Creates a Stripe Checkout session for listing upload fee payment
    listing = get_object_or_404(Listing, pk=pk, owner=request.user)

    if listing.status != Listing.Status.DRAFT:
        messages.error(request, "Only draft listings can be paid for.")
        return redirect("listings:listing_detail", pk=listing.pk)

    # Hard fail if Stripe secrets aren't set on server
    try:
        ensure_stripe_configured()
    except RuntimeError:
        messages.error(request, "Stripe is not configured on the server.")
        return redirect("listings:listing_detail", pk=listing.pk)

    # If the listing already has a usable checkout session, reuse it
    reused_url = try_reuse_existing_checkout_session(listing=listing)
    if reused_url:
        return redirect(reused_url, permanent=False)

    if listing.duration_days is None:
        messages.error(
            request, "Duration days must be set before proceeding to checkout."
        )
        return redirect("listings:listing_detail", pk=listing.pk)

    duration_days = int(listing.duration_days)

    # Pricing is calculated server-side based on funding band and duration
    try:
        amount_pence = calculate_listing_price_pence(
            funding_band=listing.funding_band,
            duration_days=duration_days,
        )
    except ValueError:
        messages.error(request, "Pricing could not "
                                "be calculated for this listing.")
        return redirect("listings:listing_detail", pk=listing.pk)
    # Redirect targets
    success_url, cancel_url = build_stripe_urls(listing=listing)

    # Create a Stripe Checkout session
    session = stripe.checkout.Session.create(
        mode="payment",
        currency="gbp",
        # Used by webhook to identify listing
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

    # Persist expected price and session id so webhook can validate later
    listing.expected_amount_pence = int(amount_pence)
    listing.stripe_checkout_session_id = session.id
    listing.save(update_fields=["expected_amount_pence",
                                "stripe_checkout_session_id"])

    return redirect(session.url, permanent=False)  # Stripe-hosted checkout URL


@login_required
def payment_success_view(request):
    # Success redirect target after Stripe payment completes
    listing_id = (request.GET.get("listing_id") or "").strip()
    session_id = (request.GET.get("session_id") or "").strip()

    if not (listing_id and session_id and settings.STRIPE_SECRET_KEY):
        messages.success(request, "Payment received. "
                                  "Your listing will activate shortly.")
        return redirect("users:dashboard")

    stripe.api_key = settings.STRIPE_SECRET_KEY

    try:
        # Server-side verification
        session = stripe.checkout.Session.retrieve(session_id)
    except stripe.error.StripeError:
        messages.success(request, "Payment received. "
                                  "Your listing will activate shortly.")
        return redirect("users:dashboard")

    # Atomic activation attempt
    # (prevents double-activate from webhook and return)
    try:
        with transaction.atomic():
            listing = Listing.objects.select_for_update().get(
                pk=listing_id, owner=request.user
            )
            activated = activate_listing_from_paid_session(
                listing=listing, session=session,
                )
    except Listing.DoesNotExist:
        activated = False

    if activated:
        messages.success(request, "Payment received. "
                                  "Your listing is now active.")
    else:
        messages.success(request, "Payment received. "
                                  "Your listing will activate shortly.")

    return redirect("users:dashboard")


@login_required
def payment_cancel_view(request, pk):
    # Cancel redirect target (user-facing): keeps listing as draft
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

    messages.info(request, "Payment cancelled. "
                           "Your listing is still saved as a draft.")
    return redirect("listings:listing_detail", pk=pk)


@csrf_exempt
@require_POST
def stripe_webhook(request):
    # Stripe server-to-server webhook endpoint
    if not settings.STRIPE_WEBHOOK_SECRET or not settings.STRIPE_SECRET_KEY:
        # Matches StripeWebhookTests expectation
        return HttpResponse(status=400)

    stripe.api_key = settings.STRIPE_SECRET_KEY

    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")

    # Verify signature and parse event
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

        # Only act on fully paid sessions
        if session.get("payment_status") != "paid":
            return HttpResponse(status=200)

        # Listing id can come from client_reference_id or metadata
        listing_id = session.get("client_reference_id") or (
            (session.get("metadata") or {}).get("listing_id")
        )
        if not listing_id:
            return HttpResponse(status=200)

        session_id = session.get("id")

        # Lock listing row to avoid double activation
        with transaction.atomic():
            listing = (
                Listing.objects
                .select_for_update()
                .filter(pk=listing_id)
                .first()
            )
            if not listing:
                return HttpResponse(status=200)

            if listing.status == Listing.Status.ACTIVE:
                return HttpResponse(status=200)

            # Safety: ignore if webhook session
            # doesn't match the one we created
            if (
                listing.stripe_checkout_session_id
                and session_id != listing.stripe_checkout_session_id
            ):
                return HttpResponse(status=200)

            activate_listing_from_paid_session(
                listing=listing,
                session=session,
            )

    return HttpResponse(status=200)


@login_required
@require_GET
def api_counties(request):
    # Used by JS dropdowns: given country -> counties list
    country = (request.GET.get("country") or "").strip().lower()
    return JsonResponse({"counties": COUNTIES_BY_COUNTRY.get(country, [])})


@login_required
@require_GET
def api_outcodes(request):
    # Used by JS dropdowns: given county -> postcode outcodes list
    county = (request.GET.get("county") or "").strip()
    return JsonResponse({"outcodes": OUTCODES_BY_COUNTY.get(county, [])})


@login_required
def search_listings_view(request):
    # Search filter page for investors
    project_name = (request.GET.get("project_name") or "").strip()
    listed_by = (request.GET.get("listed_by") or "").strip()

    source_use = (request.GET.get("source_use") or "").strip()
    target_use = (request.GET.get("target_use") or "").strip()

    country = (request.GET.get("country") or "").strip().lower()
    county = (request.GET.get("county") or "").strip()
    postcode_prefix = (request.GET.get("postcode_prefix") or "").strip()

    funding_band = (request.GET.get("funding_band") or "").strip()
    return_type = (request.GET.get("return_type") or "").strip()
    return_band = (request.GET.get("return_band") or "").strip()

    qs = (
        Listing.objects.filter(status=Listing.Status.ACTIVE)
        # Tests assert own listings excluded
        .exclude(owner=request.user)
        # Used for "listed by" display
        .select_related("owner")
        # Used for media.count in template
        .prefetch_related("media")
        .order_by("-created_at")
    )

    if project_name:
        qs = qs.filter(project_name__icontains=project_name)

    if listed_by:
        qs = qs.filter(
            Q(owner__first_name__icontains=listed_by)
            | Q(owner__last_name__icontains=listed_by)
            | Q(owner__email__icontains=listed_by)
        )

    if source_use:
        qs = qs.filter(source_use=source_use)

    if target_use:
        qs = qs.filter(target_use=target_use)

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

    if return_band:
        qs = qs.filter(return_band=return_band)

    # Pagination: 6 cards per page
    paginator = Paginator(qs, 6)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    # Attach progress % for each listing card
    for listing in page_obj.object_list:
        try:
            listing.progress_pct = (
                 _pledge_progress_for_listing(listing)["progress_pct"]
            )
        except Exception:
            listing.progress_pct = 0

    # Choices used to render dropdowns with current selection
    source_use_choices = Listing._meta.get_field("source_use").choices
    target_use_choices = Listing._meta.get_field("target_use").choices
    return_band_choices = Listing._meta.get_field("return_band").choices

    return render(
        request,
        "listings/search_listings.html",
        {
            "project_name": project_name,
            "listed_by": listed_by,
            "source_use": source_use,
            "target_use": target_use,
            "country": country,
            "county": county,
            "postcode_prefix": postcode_prefix,
            "funding_band": funding_band,
            "return_type": return_type,
            "return_band": return_band,
            "page_obj": page_obj,
            "source_use_choices": source_use_choices,
            "target_use_choices": target_use_choices,
            "country_choices": Listing.Country.choices,
            "funding_band_choices": Listing.FundingBand.choices,
            "return_type_choices": Listing.ReturnType.choices,
            "return_band_choices": return_band_choices,
        },
    )


@login_required
def opportunity_detail_view(request, pk):
    # Investor-facing listing page
    listing = get_object_or_404(
        Listing.objects.prefetch_related("media"),
        pk=pk,
        status=Listing.Status.ACTIVE,
    )

    images = listing.media.filter(
        media_type=ListingMedia.MediaType.IMAGE
    ).order_by("uploaded_at")
    documents = listing.media.filter(
        media_type=ListingMedia.MediaType.DOCUMENT
    ).order_by("uploaded_at")

    # Pledge progress context
    pledge_ctx = _pledge_progress_for_listing(listing)

    return render(
        request,
        "listings/opportunity_detail.html",
        {
            "listing": listing,
            "images": images,
            "documents": documents,
            **pledge_ctx,
        },
    )


@require_GET
@login_required
def estimate_return_view(request, pk):
    # AJAX endpoint used by pledge UI: returns JSON estimate for entered amount
    listing = get_object_or_404(Listing, pk=pk, status=Listing.Status.ACTIVE)

    raw = (request.GET.get("amount") or "").strip()
    try:
        amount = Decimal(raw)  # Parse as Decimal to avoid float inaccuracies
    except Exception:
        return JsonResponse(
            {"ok": False, "error": "Invalid amount."},
            status=400
        )

    if amount <= 0:
        return JsonResponse(
            {"ok": False, "error": "Amount must be greater than 0."},
            status=400
        )

    # Return range derived from listing.return_band
    try:
        min_pct, max_pct = get_return_pct_range(listing)
    except Exception:
        return JsonResponse(
            {"ok": False, "error": "Return band is not configured correctly."},
            status=400,
        )

    # Compute min/max profit and total
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
