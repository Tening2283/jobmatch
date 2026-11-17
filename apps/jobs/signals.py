from django.db import transaction
from django.db.models.signals import m2m_changed, post_save
from django.dispatch import receiver

from .models import JobOffer, JobSkill


def _schedule_embedding(job_id: int) -> None:
    from apps.matching.tasks import embed_job_offer

    transaction.on_commit(lambda: embed_job_offer.delay(job_id))


@receiver(post_save, sender=JobOffer)
def job_offer_saved(sender, instance: JobOffer, update_fields=None, **kwargs):
    # Les mises à jour internes de l'embedding ne doivent pas reboucler.
    if update_fields and set(update_fields) <= {"embedding", "embedding_updated_at", "is_active"}:
        return
    _schedule_embedding(instance.pk)


@receiver(post_save, sender=JobSkill)
def job_skill_saved(sender, instance: JobSkill, created, **kwargs):
    _schedule_embedding(instance.job_id)


@receiver(m2m_changed, sender=JobOffer.skills.through)
def job_skills_changed(sender, instance, action, **kwargs):
    if action in ("post_add", "post_remove", "post_clear") and isinstance(instance, JobOffer):
        _schedule_embedding(instance.pk)
