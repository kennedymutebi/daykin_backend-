"""
Integration tests that run the full pipeline end to end — create -> polish
-> tts -> mix -> call -> callback -> status webhook — with Celery tasks
executed eagerly (synchronously) and ONLY the external I/O boundaries
mocked: the LLM client, the TTS HTTP call, ffmpeg/ffprobe subprocess calls,
public storage upload, and the Africa's Talking client. Everything in
between (models, serializers, tasks, views, service wiring) runs for real.
"""
import os
import shutil
import tempfile
from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from voice_wishes.models import VoiceWish


def _mock_llm_response(text):
    block = mock.Mock()
    block.type = "text"
    block.text = text
    response = mock.Mock()
    response.content = [block]
    return response


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class VoiceWishPipelineIntegrationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)

        music_path = os.path.join(self.tmp_dir, "soft_piano.mp3")
        with open(music_path, "wb") as f:
            f.write(b"fake-music-bytes")

        self.settings_override = override_settings(
            VOICE_WISH_AUDIO_TMP_DIR=self.tmp_dir,
            VOICE_WISH_MUSIC_DIR=self.tmp_dir,
            VOICE_WISH_CALLER_ID="+256780000000",
            MEDIA_ROOT=self.tmp_dir,
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

    def _patch_ffmpeg(self, voice_duration="6.0"):
        def fake_run(cmd, **kwargs):
            if cmd[0] == "ffprobe":
                return mock.Mock(stdout=f'{{"format": {{"duration": "{voice_duration}"}}}}')
            out_path = cmd[-1]
            with open(out_path, "wb") as f:
                f.write(b"fake-mixed-audio")
            return mock.Mock(returncode=0)
        return fake_run

    @mock.patch("voice_wishes.services.voice_call_service._get_client")
    @mock.patch("voice_wishes.services.audio_mixer._upload")
    @mock.patch("voice_wishes.services.audio_mixer.subprocess.run")
    @mock.patch("voice_wishes.services.tts_service._synthesize_to_file")
    @mock.patch("voice_wishes.services.llm_service._get_client")
    def test_happy_path_reaches_calling_status(
        self, mock_llm_client, mock_tts_write, mock_ffmpeg, mock_upload, mock_at_client
    ):
        # LLM polishing
        mock_client = mock.Mock()
        mock_client.messages.create.return_value = _mock_llm_response(
            "Wishing you joy and laughter today!"
        )
        mock_llm_client.return_value = mock_client

        # TTS writes a real (fake) file to disk
        def fake_tts_write(text, out_path):
            with open(out_path, "wb") as f:
                f.write(b"fake-voice-audio")
        mock_tts_write.side_effect = fake_tts_write

        # ffmpeg/ffprobe: voice comes in at 6s, well under the 10.5s cap
        mock_ffmpeg.side_effect = self._patch_ffmpeg(voice_duration="6.0")

        # Storage upload returns a public URL
        mock_upload.return_value = "https://cdn.example.com/voice_wishes/final.mp3"

        # Africa's Talking places the call
        mock_at = mock.Mock()
        mock_at.call.return_value = {"entries": [{"sessionId": "sess-999"}]}
        mock_at_client.return_value = mock_at

        response = self.client.post(
            reverse("voice_wishes:create"),
            {
                "sender_name": "Kennedy",
                "recipient_number": "+256700000000",
                "raw_text": "happy bday man, hope its a great one",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)

        wish = VoiceWish.objects.get(id=response.data["id"])
        self.assertEqual(wish.status, VoiceWish.Status.CALLING)
        self.assertEqual(wish.call_session_id, "sess-999")
        self.assertEqual(wish.polished_text, "Wishing you joy and laughter today!")
        self.assertEqual(wish.final_audio_url, "https://cdn.example.com/voice_wishes/final.mp3")
        self.assertIsNotNone(wish.audio_duration_seconds)

        # Provider hits the callback when the call connects
        callback_response = self.client.post(
            reverse("voice_wishes:voice-callback"), {"sessionId": "sess-999"}
        )
        content = callback_response.content.decode()
        self.assertIn(
            '<Play url="https://cdn.example.com/voice_wishes/final.mp3"/>', content
        )
        self.assertNotIn("GetDigits", content)
        self.assertNotIn("Record", content)

        # Provider hits the status webhook when the call ends
        self.client.post(
            reverse("voice_wishes:voice-status"),
            {"sessionId": "sess-999", "durationStatus": "Success"},
        )
        wish.refresh_from_db()
        self.assertEqual(wish.status, VoiceWish.Status.DELIVERED)

    @mock.patch("voice_wishes.services.voice_call_service._get_client")
    @mock.patch("voice_wishes.services.audio_mixer._upload")
    @mock.patch("voice_wishes.services.audio_mixer.subprocess.run")
    @mock.patch("voice_wishes.services.tts_service._synthesize_to_file")
    @mock.patch("voice_wishes.services.llm_service._get_client")
    def test_over_budget_audio_shrinks_and_retries_then_succeeds(
        self, mock_llm_client, mock_tts_write, mock_ffmpeg, mock_upload, mock_at_client
    ):
        # First LLM call returns long text, second (retry) returns short text.
        mock_client = mock.Mock()
        mock_client.messages.create.side_effect = [
            _mock_llm_response("A very long wish that will not fit the time budget at all"),
            _mock_llm_response("Happy birthday, enjoy your day!"),
        ]
        mock_llm_client.return_value = mock_client

        def fake_tts_write(text, out_path):
            with open(out_path, "wb") as f:
                f.write(b"fake-voice-audio")
        mock_tts_write.side_effect = fake_tts_write

        # First duration check: too long (12s) -> triggers retry+shrink.
        # After the retry, ffprobe reports a short duration (5s) that passes.
        # ffprobe is called once for the too-long attempt, once for the
        # retry attempt, once inside mix() for fade timing, and once more
        # by mix_audio to record the final mixed duration.
        durations = iter(["12.0", "5.0", "5.0", "5.0"])

        def fake_run(cmd, **kwargs):
            if cmd[0] == "ffprobe":
                return mock.Mock(stdout=f'{{"format": {{"duration": "{next(durations)}"}}}}')
            out_path = cmd[-1]
            with open(out_path, "wb") as f:
                f.write(b"fake-mixed-audio")
            return mock.Mock(returncode=0)

        mock_ffmpeg.side_effect = fake_run
        mock_upload.return_value = "https://cdn.example.com/voice_wishes/final.mp3"

        mock_at = mock.Mock()
        mock_at.call.return_value = {"entries": [{"sessionId": "sess-retry"}]}
        mock_at_client.return_value = mock_at

        response = self.client.post(
            reverse("voice_wishes:create"),
            {
                "sender_name": "Kennedy",
                "recipient_number": "+256700000000",
                "raw_text": "wish someone a happy birthday in a heartfelt way",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)

        wish = VoiceWish.objects.get(id=response.data["id"])
        self.assertEqual(wish.retry_count, 1)
        self.assertEqual(wish.status, VoiceWish.Status.CALLING)
        self.assertEqual(wish.polished_text, "Happy birthday, enjoy your day!")

    @mock.patch("voice_wishes.services.llm_service._get_client")
    def test_llm_failure_leaves_wish_in_failed_state(self, mock_llm_client):
        mock_client = mock.Mock()
        mock_client.messages.create.side_effect = RuntimeError("provider outage")
        mock_llm_client.return_value = mock_client

        response = self.client.post(
            reverse("voice_wishes:create"),
            {
                "sender_name": "Kennedy",
                "recipient_number": "+256700000000",
                "raw_text": "happy birthday!",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)

        wish = VoiceWish.objects.get(id=response.data["id"])
        self.assertEqual(wish.status, VoiceWish.Status.FAILED)
        self.assertIn("provider outage", wish.failure_reason)
