import re

from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

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

if settings.SERVE_MEDIA:       # the public screenshots only (MEDIA_ROOT); PRIVATE_MEDIA_ROOT has no route at all
    urlpatterns.append(re_path(rf"^{re.escape(settings.MEDIA_URL.lstrip('/'))}(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}))

# Grandma's error pages (pages/views.py). 405 and the CSRF failure have no handler setting here: pages/middleware.py and CSRF_FAILURE_VIEW.
handler400 = "pages.views.bad_request"
handler403 = "pages.views.permission_denied"
handler404 = "pages.views.not_found"
handler500 = "pages.views.server_error"
