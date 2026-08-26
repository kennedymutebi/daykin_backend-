from celery import shared_task
from datetime import timedelta
from django.utils import timezone
from .models import Celebrant


@shared_task
def process_birthday_celebrations():
    now = timezone.now()
    today = timezone.localdate()

    # Step 1: flag anyone whose birthday is today and hasn't been triggered yet
    Celebrant.objects.filter(
        birth_month=today.month,
        birth_day=today.day,
        celebration_triggered_at__isnull=True,
    ).update(celebration_triggered_at=now)

    # Step 2: delete anyone whose 24-hour window has expired
    cutoff = now - timedelta(hours=24)
    Celebrant.objects.filter(
        celebration_triggered_at__isnull=False,
        celebration_triggered_at__lte=cutoff,
    ).delete()