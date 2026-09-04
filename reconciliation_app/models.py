from django.db import models


class Source(models.Model):
    name = models.CharField(max_length=100)
    source_type = models.CharField(max_length=50)

    def __str__(self):
        return self.name


class File(models.Model):
    source = models.ForeignKey(
        Source,
        on_delete=models.PROTECT,
        related_name="files",
    )
    filename = models.CharField(max_length=255)
    file_hash = models.CharField(max_length=64)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source", "file_hash"],
                name="unique_source_file_hash",
            )
        ]

    def __str__(self):
        return self.filename


class Transaction(models.Model):
    source = models.ForeignKey(
        Source,
        on_delete=models.PROTECT,
        related_name="transactions",
    )
    source_reference = models.CharField(max_length=255)
    current_version = models.ForeignKey(
        "TransactionVersion",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="current_for_transactions",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source", "source_reference"],
                name="unique_source_reference",
            )
        ]

    def __str__(self):
        return self.source_reference


class TransactionVersion(models.Model):
    transaction = models.ForeignKey(
        Transaction,
        on_delete=models.PROTECT,
        related_name="versions",
    )
    file = models.ForeignKey(
        File,
        on_delete=models.PROTECT,
        related_name="transaction_versions",
    )

    version_number = models.PositiveIntegerField()

    timestamp = models.DateTimeField()
    instrument = models.CharField(max_length=100)
    side = models.CharField(max_length=10)
    quantity = models.DecimalField(
        max_digits=20,
        decimal_places=8,
    )
    unit_price = models.DecimalField(
        max_digits=20,
        decimal_places=8,
    )
    amount = models.DecimalField(
        max_digits=20,
        decimal_places=8,
    )
    status = models.CharField(max_length=30)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["transaction", "version_number"],
                name="unique_transaction_version",
            )
        ]
        ordering = ["transaction_id", "version_number"]


class RuleSet(models.Model):
    name = models.CharField(max_length=100)
    version = models.PositiveIntegerField()

    amount_tolerance = models.DecimalField(
        max_digits=20,
        decimal_places=8,
    )
    price_tolerance = models.DecimalField(
        max_digits=20,
        decimal_places=8,
    )
    quantity_tolerance = models.DecimalField(
        max_digits=20,
        decimal_places=8,
    )
    time_tolerance_seconds = models.PositiveIntegerField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["name", "version"],
                name="unique_ruleset_version",
            )
        ]


class ReconciliationRun(models.Model):
    class Status(models.TextChoices):
        RUNNING = "RUNNING"
        COMPLETED = "COMPLETED"
        FAILED = "FAILED"

    our_file = models.ForeignKey(
        File,
        on_delete=models.PROTECT,
        related_name="our_runs",
    )
    external_file = models.ForeignKey(
        File,
        on_delete=models.PROTECT,
        related_name="external_runs",
    )
    ruleset = models.ForeignKey(
        RuleSet,
        on_delete=models.PROTECT,
        related_name="runs",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.RUNNING,
    )

    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)


class ReconciliationResult(models.Model):
    class Status(models.TextChoices):
        MATCHED = "MATCHED"
        MATCHED_WITH_DIFFERENCES = "MATCHED_WITH_DIFFERENCES"
        NEEDS_REVIEW = "NEEDS_REVIEW"
        UNMATCHED_OUR_SIDE = "UNMATCHED_OUR_SIDE"
        UNMATCHED_EXTERNAL_SIDE = "UNMATCHED_EXTERNAL_SIDE"
        EXCLUDED = "EXCLUDED"

    run = models.ForeignKey(
        ReconciliationRun,
        on_delete=models.CASCADE,
        related_name="results",
    )

    our_version = models.ForeignKey(
        TransactionVersion,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="our_reconciliation_results",
    )
    external_version = models.ForeignKey(
        TransactionVersion,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="external_reconciliation_results",
    )

    status = models.CharField(
        max_length=40,
        choices=Status.choices,
    )
    match_method = models.CharField(
        max_length=50,
        null=True,
        blank=True,
    )
    confidence = models.PositiveIntegerField(null=True, blank=True)

    differences_json = models.JSONField(default=dict)
    candidates_json = models.JSONField(default=list)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["run", "our_version"],
                name="unique_run_our_version",
            ),
            models.UniqueConstraint(
                fields=["run", "external_version"],
                name="unique_run_external_version",
            ),
        ]


class ManualDecision(models.Model):
    class Decision(models.TextChoices):
        MATCH = "MATCH"
        NO_MATCH = "NO_MATCH"

    result = models.ForeignKey(
        ReconciliationResult,
        on_delete=models.CASCADE,
        related_name="manual_decisions",
    )

    our_version = models.ForeignKey(
        TransactionVersion,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="manual_our_decisions",
    )
    external_version = models.ForeignKey(
        TransactionVersion,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="manual_external_decisions",
    )

    decision = models.CharField(
        max_length=20,
        choices=Decision.choices,
    )
    reason = models.TextField(blank=True)
    decided_by = models.CharField(max_length=100)
    decided_at = models.DateTimeField(auto_now_add=True)