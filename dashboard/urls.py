from django.urls import path

from . import views

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("dashboard/submissions/", views.submissions, name="dashboard_submissions"),
    path("dashboard/cookies/", views.cookies, name="dashboard_cookies"),
]
