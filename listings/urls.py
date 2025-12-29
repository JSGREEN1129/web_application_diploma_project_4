from django.urls import path
from . import views

app_name = "listings"  # App namespace used in templates/tests: e.g. {% url 'listings:search_listings' %}

urlpatterns = [
    # --- Listing CRUD (owner-side) ---
    path("create-listing/", views.create_listing_view, name="create_listing"),  # Create a new draft listing (Step 1 flow)
    path("<int:pk>/", views.listing_detail_view, name="listing_detail"),        # Owner listing detail page (draft/active/expired)
    path("<int:pk>/edit/", views.edit_listing_view, name="edit_listing"),       # Edit an existing DRAFT listing (stepper + uploads)
    path("<int:pk>/delete/", views.listing_delete_view, name="listing_delete"), # Delete listing (usually draft-only; requires password)

    # --- Media management (owner-side) ---
    path(
        "<int:pk>/media/<int:media_id>/delete/",
        views.listing_media_delete_view,
        name="listing_media_delete",
    ),  # Delete a single media item (draft-only in your tests)

    # --- Investor discovery (authenticated users) ---
    path("search/", views.search_listings_view, name="search_listings"),  # Search/filter ACTIVE listings (your live tests hit this)
    path("opportunities/<int:pk>/", views.opportunity_detail_view, name="opportunity_detail"),  # Investor-facing detail page for ACTIVE listings

    # --- AJAX return estimate (used by pledge UI) ---
    path(
        "opportunities/<int:pk>/estimate-return/",
        views.estimate_return_view,
        name="estimate_return",
    ),  # Returns JSON estimate based on amount and listing return band (tests expect 200 and application/json)

    # --- Activation + payments (owner-side) ---
    path("<int:pk>/activate/", views.activate_listing_view, name="activate_listing"),  # Validates step completion, then sends to checkout if ready
    path("<int:pk>/checkout/", views.start_listing_checkout_view, name="listing_checkout"),  # Creates Stripe checkout session for activation fee

    # --- Payment outcomes ---
    path("payments/success/", views.payment_success_view, name="payment_success"),     # Stripe success redirect
    path("payments/cancel/<int:pk>/", views.payment_cancel_view, name="payment_cancel"),  # Stripe cancel redirect (pk keeps context)

    # --- Stripe webhook (server-to-server) ---
    path("stripe/webhook/", views.stripe_webhook, name="stripe_webhook"),  # Receives Stripe events; activates listing on paid session

    # --- Location API endpoints (used by JS to populate dropdowns) ---
    path("api/counties/", views.api_counties, name="api_counties"),  # Returns counties based on selected country
    path("api/outcodes/", views.api_outcodes, name="api_outcodes"),  # Returns postcode prefixes (outcodes) based on selected county

    # --- Stepper flags (used by listing_stepper.js to update UI state) ---
    path("api/stepper/", views.api_listing_stepper_flags, name="api_listing_stepper_flags_create"),      # Create flow (no pk yet)
    path("api/stepper/<int:pk>/", views.api_listing_stepper_flags, name="api_listing_stepper_flags_edit"),  # Edit flow (existing listing)
]
