from django.apps import AppConfig


class VoiceWishesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "voice_wishes"
    verbose_name = "Voice Wishes"

    def ready(self):
        # Import signal handlers, if any are added later.
        pass
