from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from core import views as core_views
from seulpick_api import compat_views
from seulpick_api.frontend_views import vue_index
from users import views as user_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/config/", core_views.config),
    path("api/v1/health/", core_views.health),
    path("api/v1/overview/", compat_views.overview),
    path("api/v1/places/", compat_views.places),
    path("api/v1/recommendations/", compat_views.recommendations),
    path("api/v1/videos/", core_views.videos),
    path("api/v1/community/", compat_views.community),
    path("api/v1/ai/analyze/", compat_views.ai_analyze),
    path("api/v1/auth/status/", user_views.auth_status_view),
    path("api/v1/auth/login/", user_views.login_view),
    path("api/v1/auth/register/", user_views.register_view),
    path("api/v1/auth/logout/", user_views.logout_view),
    path("api/v1/profile/update/", user_views.update_profile_view),
    path("api/v1/hyperlocal/", include("hyperlocal.urls")),
    path("api/v1/finance/", include("finance.urls")),
    path("api/v1/community/", include("community.urls")),
    path("api/v1/users/", include("users.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

urlpatterns += [
    path("", vue_index),
    path("<path:path>", vue_index),
]

