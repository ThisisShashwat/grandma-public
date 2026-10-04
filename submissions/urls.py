from django.urls import path, re_path

from . import views

urlpatterns = [
    path("submit/", views.submit, name="submit"),
    re_path(r"^submit/(?P<pk>\d{1,9})/$", views.submit, name="submit_fix"),
    path("grandma/collect/", views.collect, name="collect"),
]
