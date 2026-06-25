from django.urls import path

from .views import (
    ConsumptionProfileUpsertView,
    OwnedCardUpsertView,
    ProfileView,
    UploadedReportCreateView,
)

urlpatterns = [
    path("profile/", ProfileView.as_view(), name="profile"),
    path("owned-cards/", OwnedCardUpsertView.as_view(), name="owned-cards"),
    path(
        "consumption-profile/",
        ConsumptionProfileUpsertView.as_view(),
        name="consumption-profile",
    ),
    path("reports/", UploadedReportCreateView.as_view(), name="reports"),
]

