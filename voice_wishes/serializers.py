from rest_framework import serializers

from .models import RAW_TEXT_MAX_CHARS, VoiceWish


class VoiceWishCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = VoiceWish
        fields = ["id", "sender_name", "recipient_number", "raw_text", "music_track", "status"]
        read_only_fields = ["id", "status"]

    def validate_raw_text(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Message can't be empty.")
        if len(value) > RAW_TEXT_MAX_CHARS:
            raise serializers.ValidationError(
                f"Keep it short — max {RAW_TEXT_MAX_CHARS} characters so the "
                "call stays under 10 seconds."
            )
        return value

    def validate_sender_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Sender name can't be empty.")
        return value


class VoiceWishStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = VoiceWish
        fields = [
            "id",
            "sender_name",
            "recipient_number",
            "raw_text",
            "polished_text",
            "audio_duration_seconds",
            "status",
            "failure_reason",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
