from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

# No signup and no password reset: accounts are made in the admin for now (docs/accounts.md).
urlpatterns = [
    path("login/", views.Login.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),       # POST only (Django 5 and later), CSRF checked
    path("welcome/", views.welcome, name="welcome"),
]
