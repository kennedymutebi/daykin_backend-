from unittest import mock

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from voice_wishes.models import VoiceWish
from voice_wishes.tests.test_models import make_wish


class VoiceWishCreateViewTests(APITestCase):
    def setUp(self):
        self.url = reverse("voice_wishes:create")

    def valid_payload(self, **overrides):
        payload = {
            "sender_name": "Kennedy",
            "recipient_number": "+256700000000",
            "raw_text": "Wishing you the best day ever!",
        }
        payload.update(overrides)
        return payload

    @mock.patch("voice_wishes.views.polish_text.delay")
    def test_valid_post_creates_wish_and_queues_pipeline(self, mock_delay):
        response = self.client.post(self.url, self.valid_payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(VoiceWish.objects.count(), 1)
        wish = VoiceWish.objects.first()
        mock_delay.assert_called_once_with(str(wish.id))
        self.assertEqual(response.data["status"], VoiceWish.Status.PENDING)

    @mock.patch("voice_wishes.views.polish_text.delay")
    def test_message_over_char_cap_returns_400_and_does_not_queue(self, mock_delay):
        response = self.client.post(
            self.url, self.valid_payload(raw_text="x" * 91), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(VoiceWish.objects.count(), 0)
        mock_delay.assert_not_called()

    @mock.patch("voice_wishes.views.polish_text.delay")
    def test_invalid_phone_number_returns_400(self, mock_delay):
        response = self.client.post(
            self.url, self.valid_payload(recipient_number="abc"), format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class VoiceWishStatusViewTests(APITestCase):
    def test_returns_status_for_existing_wish(self):
        wish = make_wish(polished_text="Wishing you joy", status=VoiceWish.Status.CALLING)
        url = reverse("voice_wishes:status", args=[wish.id])

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], VoiceWish.Status.CALLING)
        self.assertEqual(response.data["polished_text"], "Wishing you joy")

    def test_returns_404_for_unknown_wish(self):
        url = reverse(
            "voice_wishes:status", args=["00000000-0000-0000-0000-000000000000"]
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class VoiceCallbackViewTests(APITestCase):
    def setUp(self):
        self.url = reverse("voice_wishes:voice-callback")

    def test_returns_play_only_xml_for_known_session(self):
        wish = make_wish(
            call_session_id="sess-123",
            final_audio_url="https://cdn.example.com/a.mp3",
            status=VoiceWish.Status.CALLING,
        )

        response = self.client.post(self.url, {"sessionId": "sess-123"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        content = response.content.decode()
        self.assertIn('<Play url="https://cdn.example.com/a.mp3"/>', content)
        self.assertNotIn("GetDigits", content)
        self.assertNotIn("Record", content)

    def test_unknown_session_returns_reject_xml(self):
        response = self.client.post(self.url, {"sessionId": "does-not-exist"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("<Reject/>", response.content.decode())


class VoiceCallStatusViewTests(APITestCase):
    def setUp(self):
        self.url = reverse("voice_wishes:voice-status")

    def test_success_status_marks_wish_delivered(self):
        wish = make_wish(call_session_id="sess-1", status=VoiceWish.Status.CALLING)

        response = self.client.post(
            self.url, {"sessionId": "sess-1", "durationStatus": "Success"}
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        wish.refresh_from_db()
        self.assertEqual(wish.status, VoiceWish.Status.DELIVERED)

    def test_no_answer_status_marks_wish_no_answer(self):
        wish = make_wish(call_session_id="sess-2", status=VoiceWish.Status.CALLING)

        self.client.post(self.url, {"sessionId": "sess-2", "durationStatus": "NoAnswer"})

        wish.refresh_from_db()
        self.assertEqual(wish.status, VoiceWish.Status.NO_ANSWER)

    def test_unknown_session_does_not_error(self):
        response = self.client.post(
            self.url, {"sessionId": "ghost", "durationStatus": "Success"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
