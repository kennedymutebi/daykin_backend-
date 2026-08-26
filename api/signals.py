# api/signals.py
from django.db.models.signals import post_delete
from django.dispatch import receiver
from .models import Celebrant


@receiver(post_delete, sender=Celebrant)
def delete_celebrant_photo_file(sender, instance, **kwargs):
    if instance.photo:
        instance.photo.delete(save=False)