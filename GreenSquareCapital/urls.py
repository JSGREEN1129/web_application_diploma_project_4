from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path("users/", include("users.urls")),
    path("investments/", include("investments.urls")),
    path("search/", include("search.urls")),
    path("", include("listings.urls")),  # homepage handled by listings
]
