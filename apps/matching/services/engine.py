"""Moteur de recommandation hybride : récupération pgvector + re-classement par règles."""

from __future__ import annotations

from dataclasses import dataclass, field

from django.conf import settings
from django.db.models import Prefetch, Q
from django.utils import timezone
from pgvector.django import CosineDistance

from apps.candidates.models import CandidateProfile
from apps.core.choices import RemoteMode
from apps.jobs.models import JobOffer, JobSkill

from . import rules


@dataclass
class Match:
    obj: object
    score: float
    breakdown: dict[str, float] = field(default_factory=dict)


def _similarity(distance) -> float:
    if distance is None:
        return 0.0
    return round(min(1.0, max(0.0, 1.0 - float(distance))), 4)


def _job_skill_sets(job: JobOffer) -> tuple[set[int], set[int]]:
    required, optional = set(), set()
    for js in job.job_skills.all():
        (required if js.required else optional).add(js.skill_id)
    return required, optional


def score_pair(
    profile: CandidateProfile,
    candidate_skills: set[int],
    job: JobOffer,
    similarity: float,
    now=None,
) -> Match:
    now = now or timezone.now()
    required, optional = _job_skill_sets(job)
    scores = {
        "semantic": similarity,
        "skills": rules.skills_score(candidate_skills, required, optional),
        "experience": rules.experience_score(profile.experience_years, job.min_experience_years),
        "location": rules.location_score(
            profile.location, profile.remote_preference, job.location, job.remote
        ),
        "salary": rules.salary_score(profile.expected_salary, job.salary_min, job.salary_max),
        "freshness": rules.freshness_score(job.created_at, now, settings.MATCHING_FRESHNESS_DAYS),
    }
    total = rules.combine(scores, settings.MATCHING_WEIGHTS)
    return Match(
        obj=job,
        score=round(total, 4),
        breakdown={k: round(v, 4) for k, v in scores.items()},
    )


def candidate_job_filters(profile: CandidateProfile) -> Q:
    """Filtres durs appliqués en SQL avant le scoring."""
    q = Q(is_active=True) & (Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))
    if profile.contract_types:
        q &= Q(contract_type__in=profile.contract_types)
    if profile.remote_preference == RemoteMode.REMOTE:
        q &= Q(remote__in=[RemoteMode.REMOTE, RemoteMode.HYBRID])
    return q


def recommend_jobs(
    profile: CandidateProfile,
    limit: int = 20,
    extra_filters: Q | None = None,
    exclude_ids: set[int] | None = None,
) -> list[Match]:
    qs = (
        JobOffer.objects.filter(candidate_job_filters(profile))
        .select_related("company")
        .prefetch_related(
            Prefetch("job_skills", queryset=JobSkill.objects.only("job_id", "skill_id", "required"))
        )
    )
    if extra_filters is not None:
        qs = qs.filter(extra_filters)
    if exclude_ids:
        qs = qs.exclude(pk__in=exclude_ids)

    pool = settings.MATCHING_CANDIDATE_POOL
    if profile.embedding is not None:
        qs = qs.annotate(distance=CosineDistance("embedding", profile.embedding)).order_by(
            "distance", "-created_at"
        )
    else:  # repli : pas encore d'embedding, on classe uniquement par règles
        qs = qs.order_by("-created_at")
    jobs = list(qs[:pool])

    candidate_skills = set(profile.skills.values_list("id", flat=True))
    now = timezone.now()
    matches = [
        score_pair(profile, candidate_skills, job, _similarity(getattr(job, "distance", None)), now)
        for job in jobs
    ]
    matches.sort(key=lambda m: m.score, reverse=True)
    return matches[:limit]


def recommend_candidates(job: JobOffer, limit: int = 20) -> list[Match]:
    qs = CandidateProfile.objects.select_related("user").prefetch_related("skills")
    qs = qs.filter(Q(contract_types=[]) | Q(contract_types__contains=[job.contract_type]))
    if job.remote == RemoteMode.ONSITE:
        qs = qs.exclude(remote_preference=RemoteMode.REMOTE)
    if job.embedding is not None:
        qs = qs.annotate(distance=CosineDistance("embedding", job.embedding)).order_by("distance")
    else:
        qs = qs.order_by("-updated_at")
    profiles = list(qs[: settings.MATCHING_CANDIDATE_POOL])

    now = timezone.now()
    matches = []
    for profile in profiles:
        skills = {s.id for s in profile.skills.all()}
        m = score_pair(profile, skills, job, _similarity(getattr(profile, "distance", None)), now)
        m.breakdown.pop("freshness", None)
        m.obj = profile
        matches.append(m)
    matches.sort(key=lambda m: m.score, reverse=True)
    return matches[:limit]
