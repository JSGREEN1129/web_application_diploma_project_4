from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core.views import custom_404

urlpatterns = [
    path("", include("core.urls")),
    path("admin/", admin.site.urls),
    path("users/", include("users.urls")),
    path("listings/", include("listings.urls")),
    path("investments/", include("investments.urls")),
]

handler404 = custom_404

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
