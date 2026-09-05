from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import File, Source, RuleSet, ReconciliationRun
from .services.file_ingestion import ingest_file
from .services.reconciliation_service import run_reconciliation


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


class ReconciliationRunCreateView(APIView):
    """
    Start a reconciliation between two uploaded files.
    """

    def post(self, request):
        our_file_id = request.data.get("our_file_id")
        external_file_id = request.data.get("external_file_id")
        ruleset_id = request.data.get("ruleset_id")

        if not our_file_id:
            return Response(
                {"error": "our_file_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not external_file_id:
            return Response(
                {"error": "external_file_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not ruleset_id:
            return Response(
                {"error": "ruleset_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            our_file = File.objects.get(id=our_file_id)
        except File.DoesNotExist:
            return Response(
                {"error": "Our file not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            external_file = File.objects.get(id=external_file_id)
        except File.DoesNotExist:
            return Response(
                {"error": "External file not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            ruleset = RuleSet.objects.get(id=ruleset_id)
        except RuleSet.DoesNotExist:
            return Response(
                {"error": "Ruleset not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        run = run_reconciliation(
            our_file=our_file,
            external_file=external_file,
            ruleset=ruleset,
        )

        return Response(
            {
                "id": run.id,
                "status": run.status,
                "our_file_id": run.our_file_id,
                "external_file_id": run.external_file_id,
                "ruleset_id": run.ruleset_id,
                "started_at": run.started_at,
                "completed_at": run.completed_at,
            },
            status=status.HTTP_201_CREATED,
        )