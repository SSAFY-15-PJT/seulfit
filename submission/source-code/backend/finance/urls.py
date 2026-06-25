from django.urls import path

from .views import CardProductListView

urlpatterns = [
    path("cards/", CardProductListView.as_view(), name="cards"),
]

