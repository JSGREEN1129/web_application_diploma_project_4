from django.urls import path

from . import views

app_name = "listings"
# App namespace used in templates/tests,
# e.g. {% url 'listings:search_listings' %}

urlpatterns = [
    # --- Listing CRUD (owner-side) ---

    # Create a new draft listing (Step 1 flow)
    path(
        "create-listing/",
        views.create_listing_view,
        name="create_listing",
    ),

    # Owner listing detail page (draft / active / expired)
    path(
        "<int:pk>/",
        views.listing_detail_view,
        name="listing_detail",
    ),

    # Edit an existing DRAFT listing (stepper and uploads)
    path(
        "<int:pk>/edit/",
        views.edit_listing_view,
        name="edit_listing",
    ),

    # Delete listing (usually draft-only; requires password)
    path(
        "<int:pk>/delete/",
        views.listing_delete_view,
        name="listing_delete",
    ),

    # --- Media management (owner-side) ---

    # Delete a single media item (draft-only in tests)
    path(
        "<int:pk>/media/<int:media_id>/delete/",
        views.listing_media_delete_view,
        name="listing_media_delete",
    ),

    # --- Investor discovery (authenticated users) ---

    # Search / filter ACTIVE listings
    path(
        "search/",
        views.search_listings_view,
        name="search_listings",
    ),

    # Investor-facing detail page for ACTIVE listings
    path(
        "opportunities/<int:pk>/",
        views.opportunity_detail_view,
        name="opportunity_detail",
    ),

    # --- AJAX return estimate (pledge UI) ---

    # Returns JSON estimate based on amount and listing return band
    path(
        "opportunities/<int:pk>/estimate-return/",
        views.estimate_return_view,
        name="estimate_return",
    ),

    # --- Activation and payments (owner-side) ---

    # Validates step completion, then sends to checkout if ready
    path(
        "<int:pk>/activate/",
        views.activate_listing_view,
        name="activate_listing",
    ),

    # Creates Stripe checkout session for activation fee
    path(
        "<int:pk>/checkout/",
        views.start_listing_checkout_view,
        name="listing_checkout",
    ),

    # --- Payment outcomes ---

    # Stripe success redirect
    path(
        "payments/success/",
        views.payment_success_view,
        name="payment_success",
    ),

    # Stripe cancel redirect (pk keeps context)
    path(
        "payments/cancel/<int:pk>/",
        views.payment_cancel_view,
        name="payment_cancel",
    ),

    # --- Stripe webhook (server-to-server) ---

    # Receives Stripe events; activates listing on paid session
    path(
        "stripe/webhook/",
        views.stripe_webhook,
        name="stripe_webhook",
    ),

    # --- Location API endpoints (used by JS) ---

    # Returns counties based on selected country
    path(
        "api/counties/",
        views.api_counties,
        name="api_counties",
    ),

    # Returns postcode prefixes (outcodes) based on selected county
    path(
        "api/outcodes/",
        views.api_outcodes,
        name="api_outcodes",
    ),

    # --- Stepper flags (used by listing_stepper.js) ---

    # Create flow (no pk yet)
    path(
        "api/stepper/",
        views.api_listing_stepper_flags,
        name="api_listing_stepper_flags_create",
    ),

    # Edit flow (existing listing)
    path(
        "api/stepper/<int:pk>/",
        views.api_listing_stepper_flags,
        name="api_listing_stepper_flags_edit",
    ),
]
