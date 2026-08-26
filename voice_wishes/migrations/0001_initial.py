import uuid

import django.core.validators
from django.db import migrations, models

import voice_wishes.models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="VoiceWish",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("sender_name", models.CharField(max_length=100)),
                (
                    "recipient_number",
                    models.CharField(
                        max_length=20,
                        validators=[voice_wishes.models.phone_validator],
                    ),
                ),
                (
                    "raw_text",
                    models.CharField(
                        max_length=90,
                        validators=[django.core.validators.MaxLengthValidator(90)],
                    ),
                ),
                ("polished_text", models.TextField(blank=True)),
                ("music_track", models.CharField(default="soft_piano.mp3", max_length=100)),
                ("voice_audio_path", models.CharField(blank=True, max_length=255)),
                ("final_audio_url", models.URLField(blank=True)),
                ("audio_duration_seconds", models.FloatField(blank=True, null=True)),
                ("call_session_id", models.CharField(blank=True, db_index=True, max_length=100)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("polishing", "Polishing Text"),
                            ("generating_audio", "Generating Audio"),
                            ("mixing", "Mixing Audio"),
                            ("calling", "Calling"),
                            ("delivered", "Delivered"),
                            ("no_answer", "No Answer"),
                            ("failed", "Failed"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("failure_reason", models.CharField(blank=True, max_length=255)),
                ("retry_count", models.PositiveSmallIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
