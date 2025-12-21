from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("", include("core.urls")),
    path("admin/", admin.site.urls),
    path("users/", include("users.urls")),
    path("listings/", include("listings.urls")),
]
