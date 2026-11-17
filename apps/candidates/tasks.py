import logging

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from apps.jobs.models import Skill

from .models import Resume
from .parsing import ResumeParsingError, extract_text, parse_resume

logger = logging.getLogger(__name__)


def _taxonomy() -> dict[str, list[str]]:
    return {s.name: list(s.aliases) for s in Skill.objects.only("name", "aliases")}


@shared_task(
    bind=True,
    acks_late=True,
    autoretry_for=(OSError,),
    retry_backoff=True,
    retry_backoff_max=300,
    max_retries=3,
)
def analyze_resume(self, resume_id: int) -> str:
    """Pipeline : lecture fichier → texte → compétences/expérience → profil → embedding."""
    try:
        resume = Resume.objects.select_related("candidate").get(pk=resume_id)
    except Resume.DoesNotExist:
        logger.warning("CV %s introuvable", resume_id)
        return "missing"

    Resume.objects.filter(pk=resume_id).update(status=Resume.Status.PROCESSING, error="")

    try:
        with resume.file.open("rb") as fh:
            content = fh.read()
        text = extract_text(content, resume.file.name)
        parsed = parse_resume(text, _taxonomy())
    except ResumeParsingError as exc:
        Resume.objects.filter(pk=resume_id).update(
            status=Resume.Status.FAILED, error=str(exc), processed_at=timezone.now()
        )
        logger.info("Échec d'analyse du CV %s : %s", resume_id, exc)
        return Resume.Status.FAILED

    with transaction.atomic():
        resume.raw_text = text
        resume.parsed_data = parsed.to_dict()
        resume.status = Resume.Status.DONE
        resume.processed_at = timezone.now()
        resume.save(
            update_fields=["raw_text", "parsed_data", "status", "processed_at", "updated_at"]
        )

        profile = resume.candidate
        profile.skills.add(*Skill.objects.filter(name__in=parsed.skills))
        if parsed.experience_years > profile.experience_years:
            profile.experience_years = parsed.experience_years
            profile.save(update_fields=["experience_years", "updated_at"])

    from apps.matching.tasks import embed_candidate_profile

    embed_candidate_profile.delay(profile.pk)
    return Resume.Status.DONE
