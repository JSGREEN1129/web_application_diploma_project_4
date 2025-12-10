from django.urls import path
from .views import homepage

app_name = "core"

urlpatterns = [
    path("", homepage, name="homepage"),
]
