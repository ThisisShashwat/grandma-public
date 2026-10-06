from django.urls import path

from . import views

urlpatterns = [
    path("grandma/", views.grandma, name="grandma"),
    path("grandma/again/", views.again, name="grandma_again"),
    path("project/", views.project, name="project"),
    path("project/edit/", views.project_edit, name="project_edit"),
    path("project/rename/", views.project_rename, name="project_rename"),
    path("project/demands/", views.project_demands, name="project_demands"),
    path("complaints/", views.complaints, name="complaints"),
]
