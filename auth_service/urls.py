from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

app_name = "auth_service"

urlpatterns = [
    path("", views.RegisterUser.as_view(), name="register-user"),
    path("verify/", views.VerifyCodeView.as_view(), name="verify-user"),
    path("login/", views.RateLimitedLoginView.as_view(), name="login-user"),
    path("home/", views.HomeView.as_view(), name="home"),
    path("logout/", LogoutView.as_view(), name="logout"),
]