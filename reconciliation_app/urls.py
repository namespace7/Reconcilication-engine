from django.urls import path

from .views import FileUploadView


urlpatterns = [
    path("files/", FileUploadView.as_view(), name="file-upload"),
]
