from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="guides"),
    path("<slug:slug>/", views.page, name="guide"),
]
