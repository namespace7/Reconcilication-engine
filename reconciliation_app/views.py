from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import File, ManualDecision, ReconciliationResult, ReconciliationRun, RuleSet, Source, Transaction
from .services.file_ingestion import ingest_file
from .services.reconciliation_service import run_reconciliation
from django.shortcuts import get_object_or_404


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

class ReconciliationRunDetailView(APIView):
    def get(self, request, run_id):
        run = get_object_or_404(
            ReconciliationRun.objects.select_related(
                "our_file",
                "external_file",
                "ruleset",
            ),
            id=run_id,
        )

        results = (
            run.results
            .select_related(
                "our_version__transaction",
                "external_version__transaction",
            )
            .all()
        )

        summary = {}
        for result in results:
            summary[result.status] = summary.get(result.status, 0) + 1

        serialized_results = []

        for result in results:
            our_transaction = None
            external_transaction = None

            if result.our_version is not None:
                our_transaction = {
                    "source_reference": (
                        result.our_version.transaction.source_reference
                    ),
                    "timestamp": result.our_version.timestamp,
                    "instrument": result.our_version.instrument,
                    "side": result.our_version.side,
                    "quantity": str(result.our_version.quantity),
                    "unit_price": str(result.our_version.unit_price),
                    "amount": str(result.our_version.amount),
                    "status": result.our_version.status,
                    "version_number": result.our_version.version_number,
                }

            if result.external_version is not None:
                external_transaction = {
                    "source_reference": (
                        result.external_version.transaction.source_reference
                    ),
                    "timestamp": result.external_version.timestamp,
                    "instrument": result.external_version.instrument,
                    "side": result.external_version.side,
                    "quantity": str(result.external_version.quantity),
                    "unit_price": str(result.external_version.unit_price),
                    "amount": str(result.external_version.amount),
                    "status": result.external_version.status,
                    "version_number": result.external_version.version_number,
                }

            serialized_results.append(
                {
                    "id": result.id,
                    "status": result.status,
                    "match_method": result.match_method,
                    "confidence": result.confidence,
                    "our_transaction": our_transaction,
                    "external_transaction": external_transaction,
                    "differences": result.differences_json,
                    "candidates": result.candidates_json,
                }
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
                "summary": summary,
                "results": serialized_results,
            }
        )

class ManualDecisionCreateView(APIView):
    def post(self, request, result_id):
        result = get_object_or_404(
            ReconciliationResult.objects.select_related(
                "run",
                "our_version__transaction",
                "external_version__transaction",
            ),
            id=result_id,
        )

        decision = request.data.get("decision")
        external_transaction_id = request.data.get("external_transaction_id")
        reason = request.data.get("reason", "")
        decided_by = request.data.get("decided_by")

        if decision not in {
            ManualDecision.Decision.MATCH,
            ManualDecision.Decision.NO_MATCH,
        }:
            return Response(
                {"error": "decision must be MATCH or NO_MATCH"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not decided_by:
            return Response(
                {"error": "decided_by is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if decision == ManualDecision.Decision.MATCH:
            if not external_transaction_id:
                return Response(
                    {
                        "error": (
                            "external_transaction_id is required "
                            "for MATCH"
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            external_transaction = get_object_or_404(
                Transaction,
                id=external_transaction_id,
            )

            if result.our_version is None:
                return Response(
                    {"error": "Result has no our-side transaction"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if result.external_version is not None:
                existing_external_id = (
                    result.external_version.transaction_id
                )
                if existing_external_id != external_transaction.id:
                    return Response(
                        {
                            "error": (
                                "External transaction does not match "
                                "the result's existing pairing"
                            )
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            our_transaction = result.our_version.transaction

        else:
            our_transaction = (
                result.our_version.transaction
                if result.our_version is not None
                else None
            )
            external_transaction = (
                result.external_version.transaction
                if result.external_version is not None
                else None
            )

        try:
            manual_decision = ManualDecision.objects.create(
                result=result,
                our_transaction=our_transaction,
                external_transaction=external_transaction,
                decision=decision,
                reason=reason,
                decided_by=decided_by,
            )
        except Exception as exc:
            # The database constraint prevents duplicate decisions
            # for the same transaction pair.
            from django.db import IntegrityError

            if isinstance(exc, IntegrityError):
                return Response(
                    {
                        "error": (
                            "A manual decision already exists "
                            "for this transaction pair"
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
            raise

        return Response(
            {
                "id": manual_decision.id,
                "result_id": result.id,
                "decision": manual_decision.decision,
                "our_transaction_id": (
                    manual_decision.our_transaction_id
                ),
                "external_transaction_id": (
                    manual_decision.external_transaction_id
                ),
                "reason": manual_decision.reason,
                "decided_by": manual_decision.decided_by,
                "decided_at": manual_decision.decided_at,
            },
            status=status.HTTP_201_CREATED,
        )