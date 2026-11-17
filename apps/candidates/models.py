from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.validators import FileExtensionValidator
from django.db import models
from pgvector.django import VectorField

from apps.core.choices import ContractType, RemoteMode
from apps.core.models import TimeStampedModel
from apps.jobs.models import Skill


class CandidateProfile(TimeStampedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="candidate_profile"
    )
    headline = models.CharField(max_length=200, blank=True)
    summary = models.TextField(blank=True)
    location = models.CharField(max_length=120, blank=True)
    remote_preference = models.CharField(
        max_length=10, choices=RemoteMode.choices, default=RemoteMode.HYBRID
    )
    contract_types = ArrayField(
        models.CharField(max_length=20, choices=ContractType.choices), default=list, blank=True
    )
    expected_salary = models.PositiveIntegerField(null=True, blank=True)
    experience_years = models.PositiveSmallIntegerField(default=0)
    skills = models.ManyToManyField(Skill, related_name="candidates", blank=True)
    embedding = VectorField(dimensions=settings.EMBEDDING_DIMENSIONS, null=True, blank=True)
    embedding_updated_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"Profil de {self.user.email}"

    def embedding_text(self) -> str:
        skills = ", ".join(s.name for s in self.skills.all())
        latest = self.resumes.filter(status=Resume.Status.DONE).order_by("-created_at").first()
        cv_excerpt = latest.raw_text[:2000] if latest else ""
        return f"{self.headline}. {self.summary}. Compétences : {skills}. {cv_excerpt}"


def resume_upload_to(instance, filename: str) -> str:
    return f"resumes/{instance.candidate.user_id}/{filename}"


class Resume(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "En attente"
        PROCESSING = "processing", "En cours"
        DONE = "done", "Terminé"
        FAILED = "failed", "Échec"

    candidate = models.ForeignKey(
        CandidateProfile, on_delete=models.CASCADE, related_name="resumes"
    )
    file = models.FileField(
        upload_to=resume_upload_to,
        validators=[FileExtensionValidator(["pdf", "docx", "txt"])],
    )
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    raw_text = models.TextField(blank=True)
    parsed_data = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"CV {self.pk} ({self.status})"
