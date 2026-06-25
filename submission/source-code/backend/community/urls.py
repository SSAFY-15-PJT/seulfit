from django.urls import path

from .views import CommentCreateView, CommentDetailView, PostDetailView, PostLikeView, PostListCreateView

urlpatterns = [
    path("posts/", PostListCreateView.as_view(), name="posts"),
    path("posts/<int:post_id>/", PostDetailView.as_view(), name="post-detail"),
    path("posts/<int:post_id>/like/", PostLikeView.as_view(), name="post-like"),
    path(
        "posts/<int:post_id>/comments/",
        CommentCreateView.as_view(),
        name="post-comments",
    ),
    path(
        "posts/<int:post_id>/comments/<int:comment_id>/",
        CommentDetailView.as_view(),
        name="post-comment-detail",
    ),
]

