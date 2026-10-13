from django.urls import path, re_path

from . import hours, views

urlpatterns = [
    path("submit/", views.submit, name="submit"),
    re_path(r"^submit/(?P<pk>[0-9]{1,9})/$", views.submit, name="submit_fix"),
    path("grandma/collect/", views.collect, name="collect"),
    path("ari/result/", views.ari_result, name="ari_result"),                               # Ari's decisions, signed: 404 until ARI_ENABLED and the outbound secret (submissions/ari_inbound.py)
    path("hackatime/check/", hours.check, name="hackatime_check"),                             # pick Hackatime projects and count hours: 404 until it is switched on (submissions/hours.py)
]
