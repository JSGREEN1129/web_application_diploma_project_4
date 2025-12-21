from django.urls import path
from .views import (
    register_view,
    login_view,
    logout_view,
    dashboard_view,
)

app_name = "users"

urlpatterns = [
    path("login/", login_view, name="login"),
    path("register/", register_view, name="register"),
    path("logout/", logout_view, name="logout"),
    path("dashboard/", dashboard_view, name="dashboard"),
]
