from django.http import HttpResponse
from django.urls import path

# placeholder until the dashboard is built
urlpatterns = [
    path("dashboard/", lambda request: HttpResponse("dashboard"), name="dashboard"),
    path("dashboard/submissions/", lambda request: HttpResponse("submissions"), name="dashboard_submissions"),
    path("dashboard/cookies/", lambda request: HttpResponse("cookies"), name="dashboard_cookies"),
]
