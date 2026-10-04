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
    path("", include("orders.urls")),
    path("", include("showcase.urls")),
    path("shop/", include("shop.urls")),
    path("guides/", include("guides.urls")),
    path("", include("pages.urls")),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)    # an empty list unless DEBUG is on

# Grandma's error pages (pages/views.py). 405 and the CSRF failure have no handler setting here: pages/middleware.py and CSRF_FAILURE_VIEW.
handler400 = "pages.views.bad_request"
handler403 = "pages.views.permission_denied"
handler404 = "pages.views.not_found"
handler500 = "pages.views.server_error"
