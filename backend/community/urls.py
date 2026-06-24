from django.urls import path

from .views import CommentCreateView, PostDetailView, PostListCreateView

urlpatterns = [
    path("posts/", PostListCreateView.as_view(), name="posts"),
    path("posts/<int:post_id>/", PostDetailView.as_view(), name="post-detail"),
    path(
        "posts/<int:post_id>/comments/",
        CommentCreateView.as_view(),
        name="post-comments",
    ),
]

