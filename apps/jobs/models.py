from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models
from pgvector.django import HnswIndex, VectorField

from apps.core.choices import ContractType, RemoteMode
from apps.core.models import TimeStampedModel


class Skill(models.Model):
    name = models.CharField(max_length=100, unique=True)
    aliases = ArrayField(models.CharField(max_length=100), default=list, blank=True)
    category = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class Company(TimeStampedModel):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    website = models.URLField(blank=True)
    location = models.CharField(max_length=120, blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="companies"
    )

    class Meta:
        ordering = ("name",)
        verbose_name_plural = "companies"

    def __str__(self) -> str:
        return self.name


class JobOffer(TimeStampedModel):
    title = models.CharField(max_length=200)
    description = models.TextField()
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="offers")
    recruiter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="job_offers"
    )
    skills = models.ManyToManyField(Skill, through="JobSkill", related_name="offers", blank=True)
    min_experience_years = models.PositiveSmallIntegerField(default=0)
    location = models.CharField(max_length=120, blank=True)
    remote = models.CharField(max_length=10, choices=RemoteMode.choices, default=RemoteMode.ONSITE)
    contract_type = models.CharField(
        max_length=20, choices=ContractType.choices, default=ContractType.CDI
    )
    salary_min = models.PositiveIntegerField(null=True, blank=True)
    salary_max = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    embedding = VectorField(dimensions=settings.EMBEDDING_DIMENSIONS, null=True, blank=True)
    embedding_updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            HnswIndex(
                name="joboffer_embedding_hnsw",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            ),
        ]

    def __str__(self) -> str:
        return f"{self.title} @ {self.company}"

    def embedding_text(self) -> str:
        skills = ", ".join(s.name for s in self.skills.all())
        return f"{self.title}. {self.description}. Compétences : {skills}"


class JobSkill(models.Model):
    job = models.ForeignKey(JobOffer, on_delete=models.CASCADE, related_name="job_skills")
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE)
    required = models.BooleanField(default=True)

    class Meta:
        unique_together = ("job", "skill")

    def __str__(self) -> str:
        return f"{self.skill_id} ({'requis' if self.required else 'optionnel'})"
