from django.urls import path, re_path

from . import views

# The address of a person or a project is /u/<id>-<slug>/ or /p/<id>-<slug>/. The slug is only decoration: whatever it says, the page
# answers at the address the server computes from the name, and every other slug is a 301 to it. The id is capped at nine digits.
urlpatterns = [
    re_path(r"^u/(?P<pk>\d{1,9})-(?P<slug>[^/]*)/$", views.profile, name="public_profile"),
    re_path(r"^u/(?P<pk>\d{1,9})/$", views.profile, name="public_profile_bare"),
    re_path(r"^p/(?P<pk>\d{1,9})-(?P<slug>[^/]*)/$", views.project, name="public_project"),
    re_path(r"^p/(?P<pk>\d{1,9})/$", views.project, name="public_project_bare"),
    path("ribbons/", views.ribbons, name="ribbons"),
    path("leaderboard/", views.leaderboard, name="leaderboard"),
]
