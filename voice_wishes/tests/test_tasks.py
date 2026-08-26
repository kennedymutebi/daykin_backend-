from unittest import mock

from django.test import TestCase, override_settings

from voice_wishes import tasks
from voice_wishes.models import MAX_POLISH_RETRIES, VoiceWish
from voice_wishes.services import audio_mixer, llm_service, tts_service, voice_call_service
from voice_wishes.tests.test_models import make_wish


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class PolishTextTaskTests(TestCase):
    @mock.patch("voice_wishes.tasks.generate_audio.delay")
    @mock.patch("voice_wishes.tasks.llm_service.rewrite_emotional")
    def test_success_sets_polished_text_and_chains_next_task(self, mock_rewrite, mock_next):
        wish = make_wish()
        mock_rewrite.return_value = "Wishing you a wonderful day!"

        tasks.polish_text(str(wish.id))

        wish.refresh_from_db()
        self.assertEqual(wish.polished_text, "Wishing you a wonderful day!")
        self.assertEqual(wish.status, VoiceWish.Status.POLISHING)
        mock_next.assert_called_once_with(str(wish.id))

    @mock.patch("voice_wishes.tasks.generate_audio.delay")
    @mock.patch("voice_wishes.tasks.llm_service.rewrite_emotional")
    def test_llm_error_marks_wish_failed_and_does_not_chain(self, mock_rewrite, mock_next):
        wish = make_wish()
        mock_rewrite.side_effect = llm_service.LLMServiceError("boom")

        tasks.polish_text(str(wish.id))

        wish.refresh_from_db()
        self.assertEqual(wish.status, VoiceWish.Status.FAILED)
        self.assertIn("boom", wish.failure_reason)
        mock_next.assert_not_called()

    def test_missing_wish_is_a_noop(self):
        # should not raise
        tasks.polish_text("00000000-0000-0000-0000-000000000000")


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class GenerateAudioTaskTests(TestCase):
    @mock.patch("voice_wishes.tasks.mix_audio.delay")
    @mock.patch("voice_wishes.tasks.audio_mixer.get_duration", return_value=6.0)
    @mock.patch("voice_wishes.tasks.tts_service.synthesize_wish", return_value="/tmp/voice.mp3")
    def test_success_within_duration_chains_mix(self, mock_tts, mock_duration, mock_next):
        wish = make_wish(polished_text="Wishing you joy")

        tasks.generate_audio(str(wish.id))

        wish.refresh_from_db()
        self.assertEqual(wish.voice_audio_path, "/tmp/voice.mp3")
        self.assertEqual(wish.status, VoiceWish.Status.GENERATING_AUDIO)
        mock_next.assert_called_once_with(str(wish.id))

    @mock.patch("voice_wishes.tasks.polish_text.delay")
    @mock.patch("voice_wishes.tasks.audio_mixer.get_duration", return_value=15.0)
    @mock.patch("voice_wishes.tasks.tts_service.synthesize_wish", return_value="/tmp/voice.mp3")
    def test_over_duration_retries_with_shrunk_word_budget(self, mock_tts, mock_duration, mock_polish):
        wish = make_wish(polished_text="A very long polished wish that runs too long")

        tasks.generate_audio(str(wish.id))

        wish.refresh_from_db()
        self.assertEqual(wish.retry_count, 1)
        mock_polish.assert_called_once()
        args, kwargs = mock_polish.call_args
        self.assertEqual(args[0], str(wish.id))
        self.assertLess(kwargs["max_words"], tasks.INITIAL_MAX_WORDS)

    @mock.patch("voice_wishes.tasks.mix_audio.delay")
    @mock.patch("voice_wishes.tasks.audio_mixer.get_duration", return_value=15.0)
    @mock.patch("voice_wishes.tasks.tts_service.synthesize_wish", return_value="/tmp/voice.mp3")
    def test_over_duration_after_max_retries_marks_failed(self, mock_tts, mock_duration, mock_next):
        wish = make_wish(polished_text="Still too long", retry_count=MAX_POLISH_RETRIES)

        tasks.generate_audio(str(wish.id))

        wish.refresh_from_db()
        self.assertEqual(wish.status, VoiceWish.Status.FAILED)
        self.assertEqual(wish.failure_reason, "audio_too_long_after_retries")
        mock_next.assert_not_called()

    @mock.patch("voice_wishes.tasks.tts_service.synthesize_wish")
    def test_tts_error_marks_wish_failed(self, mock_tts):
        wish = make_wish(polished_text="Wishing you joy")
        mock_tts.side_effect = tts_service.TTSServiceError("provider down")

        tasks.generate_audio(str(wish.id))

        wish.refresh_from_db()
        self.assertEqual(wish.status, VoiceWish.Status.FAILED)
        self.assertIn("provider down", wish.failure_reason)


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class MixAudioTaskTests(TestCase):
    @mock.patch("voice_wishes.tasks.place_call.delay")
    @mock.patch("voice_wishes.tasks.audio_mixer.get_duration", return_value=9.5)
    @mock.patch("voice_wishes.tasks.audio_mixer.upload_public", return_value="https://cdn.example.com/a.mp3")
    @mock.patch("voice_wishes.tasks.audio_mixer.mix", return_value="/tmp/mixed.mp3")
    def test_success_chains_place_call(self, mock_mix, mock_upload, mock_duration, mock_next):
        wish = make_wish(voice_audio_path="/tmp/voice.mp3")

        tasks.mix_audio(str(wish.id))

        wish.refresh_from_db()
        self.assertEqual(wish.final_audio_url, "https://cdn.example.com/a.mp3")
        self.assertEqual(wish.audio_duration_seconds, 9.5)
        self.assertEqual(wish.status, VoiceWish.Status.MIXING)
        mock_next.assert_called_once_with(str(wish.id))

    @mock.patch("voice_wishes.tasks.audio_mixer.mix")
    def test_mixing_error_marks_wish_failed(self, mock_mix):
        wish = make_wish(voice_audio_path="/tmp/voice.mp3")
        mock_mix.side_effect = audio_mixer.AudioMixerError("ffmpeg exploded")

        tasks.mix_audio(str(wish.id))

        wish.refresh_from_db()
        self.assertEqual(wish.status, VoiceWish.Status.FAILED)
        self.assertIn("ffmpeg exploded", wish.failure_reason)


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class PlaceCallTaskTests(TestCase):
    @mock.patch("voice_wishes.tasks.voice_call_service.place_call", return_value="sess-123")
    def test_success_sets_session_id_and_calling_status(self, mock_place_call):
        wish = make_wish(final_audio_url="https://cdn.example.com/a.mp3")

        tasks.place_call(str(wish.id))

        wish.refresh_from_db()
        self.assertEqual(wish.call_session_id, "sess-123")
        self.assertEqual(wish.status, VoiceWish.Status.CALLING)

    def test_missing_audio_url_marks_failed_without_calling_provider(self):
        wish = make_wish(final_audio_url="")

        with mock.patch("voice_wishes.tasks.voice_call_service.place_call") as mock_place_call:
            tasks.place_call(str(wish.id))
            mock_place_call.assert_not_called()

        wish.refresh_from_db()
        self.assertEqual(wish.status, VoiceWish.Status.FAILED)
        self.assertEqual(wish.failure_reason, "missing_final_audio_url")

    @mock.patch("voice_wishes.tasks.voice_call_service.place_call")
    def test_call_provider_error_marks_wish_failed(self, mock_place_call):
        wish = make_wish(final_audio_url="https://cdn.example.com/a.mp3")
        mock_place_call.side_effect = voice_call_service.VoiceCallError("network down")

        tasks.place_call(str(wish.id))

        wish.refresh_from_db()
        self.assertEqual(wish.status, VoiceWish.Status.FAILED)
        self.assertIn("network down", wish.failure_reason)
