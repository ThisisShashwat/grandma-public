from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

# Accounts are made by the first Hack Club sign-in (accounts/hca.py), staff are given the `is_staff` tick by hand in
# the admin (docs/owner.md 2026-10-05), a development account can still be made in the admin, and the person fills in
# the rest at /welcome/.
urlpatterns = [
    path("login/", views.Login.as_view(), name="login"),
    path("login/hackclub/", views.login_hackclub, name="login_hackclub"),               # Sign in with Hack Club: 404 until it is switched on (accounts/hca.py)
    path("login/hackclub/callback/", views.login_hackclub_callback, name="login_hackclub_callback"),
    path("logout/", LogoutView.as_view(), name="logout"),       # POST only (Django 5 and later), CSRF checked
    path("connect/hackatime/", views.connect_hackatime, name="connect_hackatime"),             # connecting Hackatime: 404 until it is switched on (accounts/hackatime.py)
    path("connect/hackatime/callback/", views.connect_hackatime_callback, name="connect_hackatime_callback"),
    path("csrf/", views.csrf_token, name="csrf_token"),          # the Log out button of the always identical header fetches its token here
    path("welcome/", views.welcome, name="welcome"),
    path("beta/", views.beta, name="beta"),
]
