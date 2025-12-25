from django.shortcuts import render
from listings.models import Listing

def home(request):
    featured_listings = (
        Listing.objects
        .filter(status="active")
        .order_by("?")[:3]
    )

    return render(request, "core/homepage.html", {
        "featured_listings": featured_listings,
    })

