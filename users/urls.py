from django.urls import path
from django.contrib.auth import views as auth_views

from .views import register, CustomLoginView, dashboard

app_name = "users"

urlpatterns = [
    path("register/", register, name="register"),
    path("login/", CustomLoginView.as_view(), name="login"),
    path("dashboard/", dashboard, name="dashboard"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]

