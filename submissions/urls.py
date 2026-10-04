from django.urls import path, re_path

from . import hours, views

urlpatterns = [
    path("submit/", views.submit, name="submit"),
    re_path(r"^submit/(?P<pk>[0-9]{1,9})/$", views.submit, name="submit_fix"),
    path("grandma/collect/", views.collect, name="collect"),
    path("hackatime/check/", hours.check, name="hackatime_check"),                             # counting the hours of a Hackatime project: 404 until it is switched on (submissions/hours.py)
    path("hackatime/check/callback/", hours.check_callback, name="hackatime_check_callback"),
]
