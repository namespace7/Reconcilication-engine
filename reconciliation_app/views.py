from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import File, Source
from .services.file_ingestion import ingest_file


class FileUploadView(APIView):
    """
    Upload a CSV file for a known source.

    Expected multipart fields:
        source_id: integer
        file: uploaded CSV file
    """

    def post(self, request):
        source_id = request.data.get("source_id")
        uploaded_file = request.FILES.get("file")

        if not source_id:
            return Response(
                {"error": "source_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if uploaded_file is None:
            return Response(
                {"error": "file is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            source = Source.objects.get(id=source_id)
        except Source.DoesNotExist:
            return Response(
                {"error": "Source not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        result = ingest_file(
            source=source,
            filename=uploaded_file.name,
            file_bytes=uploaded_file.read(),
        )

        file = result["file"]

        response_data = {
            "status": result["status"],
            "file": {
                "id": file.id,
                "filename": file.filename,
                "source_id": file.source_id,
                "file_hash": file.file_hash,
                "uploaded_at": file.uploaded_at,
            },
            "versions_created": len(result["versions"]),
        }

        return Response(
            response_data,
            status=(
                status.HTTP_200_OK
                if result["status"] == "DUPLICATE"
                else status.HTTP_201_CREATED
            ),
        )
