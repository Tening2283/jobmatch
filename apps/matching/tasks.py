import logging

from celery import shared_task
from django.utils import timezone

from apps.candidates.models import CandidateProfile
from apps.jobs.models import JobOffer

from .services.embedder import get_embedder

logger = logging.getLogger(__name__)


@shared_task(acks_late=True, autoretry_for=(OSError,), retry_backoff=True, max_retries=3)
def embed_job_offer(job_id: int) -> bool:
    job = JobOffer.objects.prefetch_related("skills").filter(pk=job_id).first()
    if job is None:
        return False
    vector = get_embedder().encode([job.embedding_text()])[0]
    JobOffer.objects.filter(pk=job_id).update(embedding=vector, embedding_updated_at=timezone.now())
    return True


@shared_task(acks_late=True, autoretry_for=(OSError,), retry_backoff=True, max_retries=3)
def embed_candidate_profile(profile_id: int) -> bool:
    profile = CandidateProfile.objects.prefetch_related("skills").filter(pk=profile_id).first()
    if profile is None:
        return False
    vector = get_embedder().encode([profile.embedding_text()])[0]
    CandidateProfile.objects.filter(pk=profile_id).update(
        embedding=vector, embedding_updated_at=timezone.now()
    )
    return True


@shared_task
def reindex_missing_embeddings(batch_size: int = 500) -> dict[str, int]:
    jobs = list(
        JobOffer.objects.filter(embedding__isnull=True, is_active=True).values_list(
            "pk", flat=True
        )[:batch_size]
    )
    profiles = list(
        CandidateProfile.objects.filter(embedding__isnull=True).values_list("pk", flat=True)[
            :batch_size
        ]
    )
    for pk in jobs:
        embed_job_offer.delay(pk)
    for pk in profiles:
        embed_candidate_profile.delay(pk)
    logger.info("Réindexation : %s offres, %s profils", len(jobs), len(profiles))
    return {"jobs": len(jobs), "profiles": len(profiles)}
