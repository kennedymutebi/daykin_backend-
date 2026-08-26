from django.contrib import admin

from .models import VoiceWish


@admin.register(VoiceWish)
class VoiceWishAdmin(admin.ModelAdmin):
    list_display = (
        "id", "sender_name", "recipient_number", "status",
        "audio_duration_seconds", "retry_count", "created_at",
    )
    list_filter = ("status",)
    search_fields = ("sender_name", "recipient_number", "raw_text", "call_session_id")
    readonly_fields = (
        "id", "polished_text", "voice_audio_path", "final_audio_url",
        "audio_duration_seconds", "call_session_id", "created_at", "updated_at",
    )
