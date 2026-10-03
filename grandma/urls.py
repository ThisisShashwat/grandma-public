from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("", include("accounts.urls")),
    path("", include("projects.urls")),
    path("", include("submissions.urls")),
    path("", include("dashboard.urls")),
    path("shop/", include("shop.urls")),
    path("guides/", include("guides.urls")),
    path("", include("pages.urls")),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)    # an empty list unless DEBUG is on
