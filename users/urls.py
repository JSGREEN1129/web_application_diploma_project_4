from django.urls import path
from django.contrib.auth import views as auth_views

from .views import register, CustomLoginView, home, dashboard

app_name = "users"

urlpatterns = [
    path("", home, name="home"),
    path("dashboard/", dashboard, name="dashboard"),
    path("register/", register, name="register"),
    path("login/", CustomLoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]
