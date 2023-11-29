from django.urls import re_path

from .views import ExportExcelView

app_name = "upub.api"

urlpatterns = [
    re_path(r"starting/$", ExportExcelView.as_view(), name="starting"),
]
