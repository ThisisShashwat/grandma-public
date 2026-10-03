from django.urls import path

from . import views

urlpatterns = [
    path("grandma/", views.grandma, name="grandma"),
    path("grandma/again/", views.again, name="grandma_again"),
    path("project/", views.project, name="project"),
    path("project/finish/", views.finish, name="finish_project"),
]
