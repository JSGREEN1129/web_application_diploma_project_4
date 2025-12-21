from django.urls import path
from . import views

app_name = "listings"

urlpatterns = [
    path("create-listing/", views.create_listing_view, name="create_listing"),
    path("<int:pk>/", views.listing_detail_view, name="listing_detail"),
    path("<int:pk>/edit/", views.edit_listing_view, name="listing_edit"),
    path("<int:pk>/delete/", views.listing_delete_view, name="listing_delete"),
    path(
        "<int:pk>/media/<int:media_id>/delete/",
        views.listing_media_delete_view,
        name="listing_media_delete",
    ),

    path("search/", views.search_listings_view, name="search_listings"),
    path("opportunities/<int:pk>/", views.opportunity_detail_view, name="opportunity_detail"),
    path(
        "opportunities/<int:pk>/estimate-return/",
        views.estimate_return_view,
        name="estimate_return",
    ),

    path("<int:pk>/activate/", views.activate_listing_view, name="activate_listing"),
    path("<int:pk>/checkout/", views.start_listing_checkout_view, name="listing_checkout"),

    path("payments/success/", views.payment_success_view, name="payment_success"),
    path("payments/cancel/<int:pk>/", views.payment_cancel_view, name="payment_cancel"),
    path("stripe/webhook/", views.stripe_webhook, name="stripe_webhook"),

    path("api/counties/", views.api_counties, name="api_counties"),
    path("api/outcodes/", views.api_outcodes, name="api_outcodes"),
]
