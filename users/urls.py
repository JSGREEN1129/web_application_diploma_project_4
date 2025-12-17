from django.urls import path
from . import views
from .views import (
    register_view, login_view, logout_view, dashboard_view, create_listing_view, api_counties, api_outcodes, search_listings_view,
)

app_name = 'users'

urlpatterns = [
    path('login/', login_view, name='login'),
    path('register/', register_view, name='register'),
    path('logout/', logout_view, name='logout'),
    path('dashboard/', dashboard_view, name='dashboard'),
    path('create-listing/', create_listing_view, name='create_listing'),
    path("api/counties/", api_counties, name="api_counties"),
    path("api/outcodes/", api_outcodes, name="api_outcodes"),
    path("listings/<int:pk>/", views.listing_detail_view, name="listing_detail"),
    path("listings/<int:pk>/edit/", views.edit_listing_view, name="listing_edit"),
    path("listings/<int:pk>/media/<int:media_id>/delete/", views.listing_media_delete_view, name="listing_media_delete"),
    path("listings/search/", views.search_listings_view, name="search_listings"),
    path("listings/<int:pk>/checkout/", views.start_listing_checkout_view, name="listing_checkout"),
    path("stripe/webhook/", views.stripe_webhook, name="stripe_webhook"),
    path("payments/success/", views.payment_success_view, name="payment_success"),
    path("payments/cancel/<int:pk>/", views.payment_cancel_view, name="payment_cancel"),   

]
