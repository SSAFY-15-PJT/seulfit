from django.urls import path

from . import views

urlpatterns = [
    path("parse-image/", views.ParseImageView.as_view(), name="parse-image"),
    path("simulate/", views.SimulateView.as_view(), name="simulate"),
    path("map-summary/", views.MapSummaryView.as_view(), name="map-summary"),
    path("weather-curation/", views.WeatherCurationView.as_view(), name="weather-curation"),
]

