from django.urls import re_path

from .views import StartingView

app_name = "upub.api"

urlpatterns = [
    re_path(r"starting/$", StartingView.as_view(), name="starting"),
]
