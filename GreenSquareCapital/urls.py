from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
    path("users/", include("users.urls")),
    path("listings/", include("listings.urls")),
    path("investments/", include("investments.urls")),
    path("search/", include("search.urls")),
]
