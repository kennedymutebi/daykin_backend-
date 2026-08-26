from django.test import TestCase

from voice_wishes.models import RAW_TEXT_MAX_CHARS
from voice_wishes.serializers import VoiceWishCreateSerializer


class VoiceWishCreateSerializerTests(TestCase):
    def valid_payload(self, **overrides):
        payload = {
            "sender_name": "Kennedy",
            "recipient_number": "+256700000000",
            "raw_text": "Wishing you the best day ever!",
        }
        payload.update(overrides)
        return payload

    def test_valid_payload_is_valid(self):
        serializer = VoiceWishCreateSerializer(data=self.valid_payload())
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_raw_text_exceeding_cap_is_rejected(self):
        payload = self.valid_payload(raw_text="x" * (RAW_TEXT_MAX_CHARS + 1))
        serializer = VoiceWishCreateSerializer(data=payload)
        self.assertFalse(serializer.is_valid())
        self.assertIn("raw_text", serializer.errors)

    def test_raw_text_at_exact_cap_is_valid(self):
        payload = self.valid_payload(raw_text="x" * RAW_TEXT_MAX_CHARS)
        serializer = VoiceWishCreateSerializer(data=payload)
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_blank_raw_text_is_rejected(self):
        payload = self.valid_payload(raw_text="   ")
        serializer = VoiceWishCreateSerializer(data=payload)
        self.assertFalse(serializer.is_valid())

    def test_blank_sender_name_is_rejected(self):
        payload = self.valid_payload(sender_name="   ")
        serializer = VoiceWishCreateSerializer(data=payload)
        self.assertFalse(serializer.is_valid())

    def test_status_is_read_only_and_defaults_on_save(self):
        serializer = VoiceWishCreateSerializer(data=self.valid_payload())
        serializer.is_valid(raise_exception=True)
        wish = serializer.save(status="pending")
        self.assertEqual(wish.status, "pending")
