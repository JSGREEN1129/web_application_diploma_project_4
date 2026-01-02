from django.shortcuts import render
from listings.models import Listing


def home(request):
    # Select a small set of active listings to feature on the homepage
    featured_listings = (
        Listing.objects
        .filter(status="active")   # Only show active listings
        .order_by("?")[:3]         # Randomise and limit to 3 results
    )

    return render(request, "core/homepage.html", {
        "featured_listings": featured_listings,
    })

def custom_404(request, exception):
    if request.user.is_authenticated:
        context = {
            "base_template": "core/base_users.html",
            "primary_href": "/users/dashboard/",
            "primary_label": "Return to dashboard",
            "secondary_href": None,
            "secondary_label": "",
        }
    else:
        context = {
            "base_template": "core/base_public.html",
            "primary_href": "/",
            "primary_label": "Back to homepage",
            "secondary_href": "/users/login/",
            "secondary_label": "Log in",
        }

    return render(request, "404.html", context=context, status=404)
