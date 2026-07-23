from __future__ import annotations

from django.conf import settings
from django.db import models


class AIInferenceLog(models.Model):
    """Optional audit log for AI assistant suggestions.

    This project started with heuristic AI (rule-based). This model keeps
    the door open for later ML/LLM upgrades.
    """

    USER_MODEL = getattr(settings, 'AUTH_USER_MODEL', 'auth.User')

    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    # Type tags: triage, prescription_summary, reorder_recommendation, lab_recommendation
    inference_type = models.CharField(max_length=50)

    # JSON payloads to store input/output in a structured way.
    input_payload = models.JSONField(default=dict, blank=True)
    output_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']

