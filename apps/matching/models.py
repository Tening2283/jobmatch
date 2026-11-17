from django.db import models

from apps.candidates.models import CandidateProfile
from apps.core.models import TimeStampedModel
from apps.jobs.models import JobOffer


class Recommendation(TimeStampedModel):
    candidate = models.ForeignKey(
        CandidateProfile, on_delete=models.CASCADE, related_name="recommendations"
    )
    job = models.ForeignKey(JobOffer, on_delete=models.CASCADE, related_name="recommendations")
    score = models.FloatField()
    score_breakdown = models.JSONField(default=dict)
    liked = models.BooleanField(null=True, blank=True)
    applied = models.BooleanField(default=False)

    class Meta:
        ordering = ("-score",)
        constraints = [
            models.UniqueConstraint(fields=("candidate", "job"), name="uniq_reco_candidate_job")
        ]

    def __str__(self) -> str:
        return f"{self.candidate_id} → {self.job_id} ({self.score:.2f})"
