# users/views.py

from datetime import timedelta

import stripe

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate, get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .forms import (
    CustomUserCreationForm,
    CustomAuthenticationForm,
    ListingCreateForm,
    ListingMediaForm,
)
from .models import Listing, ListingMedia
from .pricing import calculate_listing_price_pence

User = get_user_model()

MAX_IMAGE_SIZE = 5 * 1024 * 1024      # 5 MB
MAX_DOCUMENT_SIZE = 10 * 1024 * 1024  # 10 MB

ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
ALLOWED_DOCUMENT_EXTENSIONS = {"pdf", "doc", "docx"}

ALLOWED_DOCUMENT_MIME_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
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


def _reset_payment_state(listing: Listing) -> None:
    """
    Any edit/media change should invalidate any previous checkout/payment info.
    Keep listing in DRAFT until a fresh checkout completes.
    """
    listing.status = Listing.Status.DRAFT
    listing.expected_amount_pence = 0
    listing.paid_amount_pence = 0
    listing.paid_at = None
    listing.stripe_checkout_session_id = ""
    listing.stripe_payment_intent_id = ""


@never_cache
def login_view(request):
    login_form = CustomAuthenticationForm(request, data=request.POST or None)
    register_form = CustomUserCreationForm()

    if request.method == "POST" and "login_submit" in request.POST:
        email = request.POST.get("username", "").strip().lower()
        password = request.POST.get("password", "")

        if not email or not password:
            messages.error(
                request,
                "Please enter your registered email and password to login.",
            )
        else:
            user_exists = User.objects.filter(email=email).exists()

            if not user_exists:
                messages.error(
                    request,
                    "There is no account associated with the email address.",
                )
            else:
                user_auth = authenticate(
                    request, username=email, password=password)
                if user_auth is not None:
                    login(request, user_auth,
                          backend="users.backends.EmailBackend")
                    messages.success(request, "Logged in successfully!")
                    return redirect("users:dashboard")
                else:
                    messages.error(
                        request,
                        "You have entered your password incorrectly.",
                    )

    context = {
        "login_form": login_form,
        "register_form": register_form,
        "show_form": "login",
    }
    return render(request, "users/login.html", context)


@never_cache
def register_view(request):
    login_form = CustomAuthenticationForm(request)
    register_form = CustomUserCreationForm(request.POST or None)

    if request.method == "POST" and "register_submit" in request.POST:
        if register_form.is_valid():
            user = register_form.save(commit=False)
            user.username = user.email
            user.save()

            login(request, user, backend="users.backends.EmailBackend")
            messages.success(request, "Registered and logged in successfully!")
            return redirect("users:dashboard")
        else:
            messages.error(request, "Please correct the errors below.")

    context = {
        "login_form": login_form,
        "register_form": register_form,
        "show_form": "register",
    }
    return render(request, "users/register.html", context)


def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect("users:login")


@login_required
def dashboard_view(request):
    investments = []
    listings = (
        Listing.objects.filter(owner=request.user)
        .prefetch_related("media")
        .order_by("-created_at")
    )

    context = {
        "investments": investments,
        "listings": listings,
    }
    return render(request, "users/dashboard.html", context)


@login_required
def create_listing_view(request):
    if request.method == "POST":
        form = ListingCreateForm(request.POST)
        media_form = ListingMediaForm()

        if form.is_valid():
            images = request.FILES.getlist("images")
            documents = request.FILES.getlist("documents")

            try:
                validate_uploaded_files(
                    images,
                    allowed_exts=ALLOWED_IMAGE_EXTENSIONS,
                    max_size=MAX_IMAGE_SIZE,
                    mime_prefix="image/",
                    label="Images",
                    allowed_exts_label="JPG, PNG or WEBP",
                )

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
                    "users/create_listing.html",
                    {"form": form, "media_form": media_form},
                )

            listing = form.save(commit=False)
            listing.owner = request.user
            listing.status = Listing.Status.DRAFT
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

            messages.success(
                request, "Draft saved. Redirecting you to payment...")
            return redirect("users:listing_checkout", pk=listing.pk)

    else:
        form = ListingCreateForm()
        media_form = ListingMediaForm()

    return render(
        request,
        "users/create_listing.html",
        {"form": form, "media_form": media_form},
    )


@login_required
def start_listing_checkout_view(request, pk):
    """
    Create a Stripe Checkout Session for a user's draft listing.
    Listing becomes ACTIVE only after verified webhook confirms payment.
    """
    listing = get_object_or_404(Listing, pk=pk, owner=request.user)

    if listing.status not in (Listing.Status.DRAFT, Listing.Status.PENDING_PAYMENT):
        messages.error(request, "Only draft listings can be paid for.")
        return redirect("users:listing_detail", pk=listing.pk)

    duration_days = int(listing.duration_days)

    try:
        amount_pence = calculate_listing_price_pence(
            funding_band=listing.funding_band,
            duration_days=duration_days,
        )
    except ValueError:
        messages.error(
            request, "Pricing could not be calculated for this listing.")
        return redirect("users:listing_detail", pk=listing.pk)

    if not settings.STRIPE_SECRET_KEY:
        messages.error(request, "Stripe is not configured on the server.")
        return redirect("users:listing_detail", pk=listing.pk)

    stripe.api_key = settings.STRIPE_SECRET_KEY

    success_url = settings.SITE_URL + reverse("users:payment_success")
    cancel_url = settings.SITE_URL + reverse(
        "users:payment_cancel", kwargs={"pk": listing.pk}
    )

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
    listing.status = Listing.Status.PENDING_PAYMENT
    listing.save(
        update_fields=["expected_amount_pence",
                       "stripe_checkout_session_id", "status"]
    )

    return redirect(session.url, permanent=False)


@login_required
def payment_success_view(request):
    messages.success(
        request, "Payment received. Your listing will activate shortly.")
    return redirect("users:dashboard")


@login_required
def payment_cancel_view(request, pk):
    """
    If they cancel payment, return listing to DRAFT so it's not stuck in pending state.
    """
    listing = get_object_or_404(Listing, pk=pk, owner=request.user)

    if listing.status == Listing.Status.PENDING_PAYMENT:
        _reset_payment_state(listing)
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

    messages.info(
        request, "Payment cancelled. Your listing is still saved as a draft.")
    return redirect("users:listing_detail", pk=pk)


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

        listing_id = session.get("client_reference_id") or (
            session.get("metadata") or {}
        ).get("listing_id")
        if not listing_id:
            return HttpResponse(status=200)

        amount_total = session.get("amount_total")
        payment_intent = session.get("payment_intent")
        session_id = session.get("id")

        with transaction.atomic():
            listing = Listing.objects.select_for_update().filter(pk=listing_id).first()
            if not listing:
                return HttpResponse(status=200)

            if listing.status == Listing.Status.ACTIVE:
                return HttpResponse(status=200)

            if listing.stripe_checkout_session_id and session_id != listing.stripe_checkout_session_id:
                return HttpResponse(status=200)

            if amount_total is None or int(amount_total) != int(listing.expected_amount_pence):
                return HttpResponse(status=200)

            now = timezone.now()
            listing.paid_amount_pence = int(amount_total)
            listing.paid_at = now
            listing.stripe_payment_intent_id = str(payment_intent or "")

            listing.status = Listing.Status.ACTIVE
            listing.active_from = now
            listing.active_until = now + \
                timedelta(days=int(listing.duration_days))

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

    return HttpResponse(status=200)


@login_required
def listing_detail_view(request, pk):
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

    return render(
        request,
        "users/listing_detail.html",
        {
            "listing": listing,
            "images": images,
            "documents": documents,
        },
    )


@login_required
def edit_listing_view(request, pk):
    listing = get_object_or_404(
        Listing.objects.prefetch_related("media"),
        pk=pk,
        owner=request.user,
    )

    if listing.status not in (Listing.Status.DRAFT, Listing.Status.PENDING_PAYMENT):
        messages.error(request, "Only draft listings can be edited.")
        return redirect("users:listing_detail", pk=listing.pk)

    images_qs = listing.media.filter(
        media_type=ListingMedia.MediaType.IMAGE
    ).order_by("uploaded_at")
    documents_qs = listing.media.filter(
        media_type=ListingMedia.MediaType.DOCUMENT
    ).order_by("uploaded_at")

    if request.method == "POST":
        form = ListingCreateForm(request.POST, instance=listing)
        media_form = ListingMediaForm()

        if form.is_valid():
            images = request.FILES.getlist("images")
            documents = request.FILES.getlist("documents")

            try:
                validate_uploaded_files(
                    images,
                    allowed_exts=ALLOWED_IMAGE_EXTENSIONS,
                    max_size=MAX_IMAGE_SIZE,
                    mime_prefix="image/",
                    label="Images",
                    allowed_exts_label="JPG, PNG or WEBP",
                )

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
                    "users/edit_listing.html",
                    {
                        "form": form,
                        "media_form": media_form,
                        "listing": listing,
                        "images": images_qs,
                        "documents": documents_qs,
                    },
                )

            listing = form.save(commit=False)

            _reset_payment_state(listing)
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

            messages.success(
                request, "Draft updated. Redirecting you to payment...")
            return redirect("users:listing_checkout", pk=listing.pk)

    else:
        form = ListingCreateForm(instance=listing)
        media_form = ListingMediaForm()

    return render(
        request,
        "users/edit_listing.html",
        {
            "form": form,
            "media_form": media_form,
            "listing": listing,
            "images": images_qs,
            "documents": documents_qs,
        },
    )


@require_POST
@login_required
def listing_media_delete_view(request, pk, media_id):
    listing = get_object_or_404(Listing, pk=pk, owner=request.user)

    if listing.status not in (Listing.Status.DRAFT, Listing.Status.PENDING_PAYMENT):
        messages.error(request, "Only draft listings can be edited.")
        return redirect("users:listing_detail", pk=listing.pk)

    media = get_object_or_404(ListingMedia, pk=media_id, listing=listing)

    media.file.delete(save=False)
    media.delete()

    if listing.status == Listing.Status.PENDING_PAYMENT:
        _reset_payment_state(listing)
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

    messages.success(request, "File deleted.")
    return redirect("users:listing_edit", pk=listing.pk)


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


@require_GET
@login_required
def api_counties(request):
    country = (request.GET.get("country") or "").strip().lower()
    return JsonResponse({"counties": COUNTIES_BY_COUNTRY.get(country, [])})


@require_GET
@login_required
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
        "users/search_listings.html",
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
