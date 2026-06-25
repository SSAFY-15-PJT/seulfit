from django.urls import path

from . import interactive_views
from . import views


urlpatterns = [
    path("config/", views.config),
    path("health/", views.health),
    path("overview/", views.overview),
    path("places/", views.places),
    path("recommendations/", views.recommendations),
    path("videos/", views.videos),
    path("community/", views.community),
    path("profile/", views.profile),
    path("ai/analyze/", views.ai_analyze),
    path("auth/status/", interactive_views.auth_status),
    path("auth/register/", interactive_views.register),
    path("auth/login/", interactive_views.login),
    path("auth/logout/", interactive_views.logout),
    path("profile/update/", interactive_views.update_profile),
    path("community/posts/", interactive_views.community_posts),
    path("community/posts/<int:post_id>/", interactive_views.community_post_detail),
    path("community/posts/<int:post_id>/comments/", interactive_views.community_comment),
]
