from django.urls import path

from .views import (FileUploadView, ReconciliationRunCreateView, ReconciliationRunDetailView, ManualDecisionCreateView, CurrentRuleSetView, RuleSetDetailView)


urlpatterns = [
    path(
        "files/",
        FileUploadView.as_view(),
        name="file-upload",
    ),
    path(
        "runs/",
        ReconciliationRunCreateView.as_view(),
        name="run-create",
    ),
    path(
        "runs/<int:run_id>/",
        ReconciliationRunDetailView.as_view(),
        name="run-detail",
    ),
    path(
        "results/<int:result_id>/decision/",
        ManualDecisionCreateView.as_view(),
        name="manual-decision-create",
    ),
    path(
        "rulesets/current/",
        CurrentRuleSetView.as_view(),
        name="current-ruleset",
    ),
    path(
        "rulesets/<int:ruleset_id>/",
        RuleSetDetailView.as_view(),
        name="ruleset-detail",
    )
]
