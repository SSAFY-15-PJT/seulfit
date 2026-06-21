from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/hyperlocal/", include("hyperlocal.urls")),
    path("api/v1/finance/", include("finance.urls")),
    path("api/v1/community/", include("community.urls")),
    path("api/v1/users/", include("users.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

