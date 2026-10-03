from django.urls import path, re_path

from . import views

urlpatterns = [
    path("grandma/", views.grandma, name="grandma"),
    path("grandma/again/", views.again, name="grandma_again"),
    path("project/", views.project, name="project"),
    re_path(r"^project/(?P<pk>\d{1,9})/finish/$", views.finish, name="finish_project"),
]
