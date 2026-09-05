from django.urls import path

from .views import FileUploadView, ReconciliationRunCreateView


urlpatterns = [
    path("files/", FileUploadView.as_view(), name="file-upload"),
    path("runs/", ReconciliationRunCreateView.as_view(), name="run-create"),

]
