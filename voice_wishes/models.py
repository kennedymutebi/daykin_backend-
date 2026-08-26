import uuid

from django.core.validators import MaxLengthValidator, RegexValidator
from django.db import models

phone_validator = RegexValidator(
    regex=r"^\+?[1-9]\d{7,14}$",
    message="Enter a valid phone number in international format, e.g. +256700000000.",
)

# Hard ceiling on raw sender input. Kept low so the final spoken message
# (intro + polished text + outro) stays comfortably inside the ~10s call budget.
RAW_TEXT_MAX_CHARS = 90

# Anything mixed audio longer than this triggers a shrink-and-retry of the
# AI polishing step, capped by MAX_POLISH_RETRIES.
MAX_CALL_DURATION_SECONDS = 10.5
MAX_POLISH_RETRIES = 2


class VoiceWish(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        POLISHING = "polishing", "Polishing Text"
        GENERATING_AUDIO = "generating_audio", "Generating Audio"
        MIXING = "mixing", "Mixing Audio"
        CALLING = "calling", "Calling"
        DELIVERED = "delivered", "Delivered"
        NO_ANSWER = "no_answer", "No Answer"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    sender_name = models.CharField(max_length=100)
    recipient_number = models.CharField(max_length=20, validators=[phone_validator])

    raw_text = models.CharField(
        max_length=RAW_TEXT_MAX_CHARS,
        validators=[MaxLengthValidator(RAW_TEXT_MAX_CHARS)],
    )
    polished_text = models.TextField(blank=True)

    music_track = models.CharField(max_length=100, default="soft_piano.mp3")

    voice_audio_path = models.CharField(max_length=255, blank=True)
    final_audio_url = models.URLField(blank=True)
    audio_duration_seconds = models.FloatField(null=True, blank=True)

    call_session_id = models.CharField(max_length=100, blank=True, db_index=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    failure_reason = models.CharField(max_length=255, blank=True)
    retry_count = models.PositiveSmallIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"VoiceWish({self.id}) to {self.recipient_number} [{self.status}]"

    def mark_failed(self, reason: str):
        self.status = self.Status.FAILED
        self.failure_reason = reason[:255]
        self.save(update_fields=["status", "failure_reason", "updated_at"])
