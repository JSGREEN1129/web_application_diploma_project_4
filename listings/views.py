from django.shortcuts import render


def listings_home(request):
    return render(request, "listings/home.html")

