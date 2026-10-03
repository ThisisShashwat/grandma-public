from django.urls import path, re_path

from . import views

urlpatterns = [
    path("grandma/", views.grandma, name="grandma"),
    path("grandma/again/", views.again, name="grandma_again"),
    path("project/", views.project, name="project"),
    path("project/edit/", views.project_edit, name="project_edit"),
    path("project/demands/", views.project_demands, name="project_demands"),
    re_path(r"^project/(?P<pk>\d{1,9})/finish/$", views.finish, name="finish_project"),
]
