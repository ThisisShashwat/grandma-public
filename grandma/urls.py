from django.conf import settings
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("", include("accounts.urls")),
    path("", include("projects.urls")),
    path("shop/", include("shop.urls")),
    path("guides/", include("guides.urls")),
    path("", include("pages.urls")),
]
