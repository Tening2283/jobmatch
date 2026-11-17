from celery import shared_task
from django.utils import timezone

from .models import JobOffer


@shared_task
def deactivate_expired_offers() -> int:
    return JobOffer.objects.filter(is_active=True, expires_at__lt=timezone.now()).update(
        is_active=False
    )
