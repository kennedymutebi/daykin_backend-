from django.core.exceptions import ValidationError
from django.test import TestCase

from voice_wishes.models import VoiceWish


def make_wish(**overrides):
    defaults = dict(
        sender_name="Kennedy",
        recipient_number="+256700000000",
        raw_text="Happy birthday, have an amazing day!",
    )
    defaults.update(overrides)
    return VoiceWish.objects.create(**defaults)


class VoiceWishModelTests(TestCase):
    def test_creates_with_default_pending_status(self):
        wish = make_wish()
        self.assertEqual(wish.status, VoiceWish.Status.PENDING)
        self.assertEqual(wish.retry_count, 0)

    def test_invalid_phone_number_fails_validation(self):
        wish = make_wish(recipient_number="not-a-number")
        with self.assertRaises(ValidationError):
            wish.full_clean()

    def test_valid_international_phone_number_passes(self):
        wish = make_wish(recipient_number="+256700000000")
        wish.full_clean()  # should not raise

    def test_raw_text_over_max_length_fails_validation(self):
        wish = make_wish(raw_text="x" * 91)
        with self.assertRaises(ValidationError):
            wish.full_clean()

    def test_mark_failed_sets_status_and_reason(self):
        wish = make_wish()
        wish.mark_failed("something broke")
        wish.refresh_from_db()
        self.assertEqual(wish.status, VoiceWish.Status.FAILED)
        self.assertEqual(wish.failure_reason, "something broke")

    def test_mark_failed_truncates_long_reason(self):
        wish = make_wish()
        wish.mark_failed("x" * 400)
        wish.refresh_from_db()
        self.assertEqual(len(wish.failure_reason), 255)

    def test_string_representation_contains_status(self):
        wish = make_wish()
        self.assertIn(wish.status, str(wish))
