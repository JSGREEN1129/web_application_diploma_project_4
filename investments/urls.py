from django.urls import path
from . import views

# Namespace for investment-related routes

app_name = "investments"

urlpatterns = [
    path("pledge/<int:listing_id>/", views.pledge_investment_view, name="pledge"),
    path("retract/<int:investment_id>/", views.retract_pledge_view, name="retract"),

]
