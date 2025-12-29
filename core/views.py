from django.shortcuts import render
from listings.models import Listing


def home(request):
    # Select a small set of active listings to feature on the homepage
    featured_listings = (
        Listing.objects
        .filter(status="active")   # Only show active listings
        .order_by("?")[:3]         # Randomise and limit to 3 results
    )

    # Render the homepage and pass featured listings to the template
    return render(request, "core/homepage.html", {
        "featured_listings": featured_listings,
    })
