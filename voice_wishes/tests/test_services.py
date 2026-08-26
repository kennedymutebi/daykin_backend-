import os
import shutil
import tempfile
from unittest import mock

from django.test import TestCase, override_settings

from voice_wishes.services import audio_mixer, llm_service, tts_service, voice_call_service


class LLMServiceTests(TestCase):
    def _mock_response(self, text):
        block = mock.Mock()
        block.type = "text"
        block.text = text
        response = mock.Mock()
        response.content = [block]
        return response

    @mock.patch("voice_wishes.services.llm_service._get_client")
    @override_settings(VOICE_WISH_LLM_MODEL="claude-test", ANTHROPIC_API_KEY="k")
    def test_rewrite_emotional_returns_stripped_text(self, mock_get_client):
        mock_client = mock.Mock()
        mock_client.messages.create.return_value = self._mock_response(' "Wishing you joy today!" ')
        mock_get_client.return_value = mock_client

        result = llm_service.rewrite_emotional("wish someone joy", max_words=10)

        self.assertEqual(result, "Wishing you joy today!")
        mock_client.messages.create.assert_called_once()

    def test_rewrite_emotional_rejects_empty_input(self):
        with self.assertRaises(llm_service.LLMServiceError):
            llm_service.rewrite_emotional("   ")

    @mock.patch("voice_wishes.services.llm_service._get_client")
    def test_rewrite_emotional_wraps_provider_errors(self, mock_get_client):
        mock_client = mock.Mock()
        mock_client.messages.create.side_effect = RuntimeError("network down")
        mock_get_client.return_value = mock_client

        with self.assertRaises(llm_service.LLMServiceError):
            llm_service.rewrite_emotional("hello there")

    @mock.patch("voice_wishes.services.llm_service._get_client")
    def test_rewrite_emotional_rejects_empty_provider_reply(self, mock_get_client):
        mock_client = mock.Mock()
        mock_client.messages.create.return_value = self._mock_response("   ")
        mock_get_client.return_value = mock_client

        with self.assertRaises(llm_service.LLMServiceError):
            llm_service.rewrite_emotional("hello there")


class TTSServiceTests(TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)

    @override_settings()
    def test_synthesize_wish_writes_and_returns_file(self):
        with override_settings(VOICE_WISH_AUDIO_TMP_DIR=self.tmp_dir):
            with mock.patch("voice_wishes.services.tts_service._synthesize_to_file") as mock_synth:
                def fake_write(text, out_path):
                    with open(out_path, "wb") as f:
                        f.write(b"fake-audio-bytes")
                mock_synth.side_effect = fake_write

                path = tts_service.synthesize_wish("Intro", "Message", "Outro")

                self.assertTrue(os.path.exists(path))
                mock_synth.assert_called_once()
                called_text = mock_synth.call_args[0][0]
                self.assertIn("Intro", called_text)
                self.assertIn("Message", called_text)
                self.assertIn("Outro", called_text)

    def test_synthesize_wish_rejects_all_blank_parts(self):
        with self.assertRaises(tts_service.TTSServiceError):
            tts_service.synthesize_wish("", "   ", "")

    def test_synthesize_wish_raises_if_provider_writes_nothing(self):
        with override_settings(VOICE_WISH_AUDIO_TMP_DIR=self.tmp_dir):
            with mock.patch("voice_wishes.services.tts_service._synthesize_to_file"):
                with self.assertRaises(tts_service.TTSServiceError):
                    tts_service.synthesize_wish("Intro", "Message", "Outro")


class AudioMixerTests(TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)

    @mock.patch("voice_wishes.services.audio_mixer.subprocess.run")
    def test_get_duration_parses_ffprobe_output(self, mock_run):
        mock_run.return_value = mock.Mock(stdout='{"format": {"duration": "7.42"}}')
        duration = audio_mixer.get_duration("/tmp/voice.mp3")
        self.assertAlmostEqual(duration, 7.42)

    @mock.patch("voice_wishes.services.audio_mixer.subprocess.run")
    def test_get_duration_raises_on_bad_output(self, mock_run):
        mock_run.return_value = mock.Mock(stdout="not json")
        with self.assertRaises(audio_mixer.AudioMixerError):
            audio_mixer.get_duration("/tmp/voice.mp3")

    def test_mix_raises_if_music_track_missing(self):
        with override_settings(
            VOICE_WISH_MUSIC_DIR=self.tmp_dir, VOICE_WISH_AUDIO_TMP_DIR=self.tmp_dir
        ):
            with self.assertRaises(audio_mixer.AudioMixerError):
                audio_mixer.mix("/tmp/voice.mp3", "missing_track.mp3")

    @mock.patch("voice_wishes.services.audio_mixer.subprocess.run")
    def test_mix_invokes_ffmpeg_and_returns_output_path(self, mock_run):
        music_path = os.path.join(self.tmp_dir, "soft_piano.mp3")
        with open(music_path, "wb") as f:
            f.write(b"fake-music")

        def fake_run(cmd, **kwargs):
            if cmd[0] == "ffprobe":
                return mock.Mock(stdout='{"format": {"duration": "5.0"}}')
            # ffmpeg call: create the declared output file
            out_path = cmd[-1]
            with open(out_path, "wb") as f:
                f.write(b"fake-mixed-audio")
            return mock.Mock(returncode=0)

        mock_run.side_effect = fake_run

        with override_settings(
            VOICE_WISH_MUSIC_DIR=self.tmp_dir, VOICE_WISH_AUDIO_TMP_DIR=self.tmp_dir
        ):
            voice_path = os.path.join(self.tmp_dir, "voice.mp3")
            with open(voice_path, "wb") as f:
                f.write(b"fake-voice")
            out_path = audio_mixer.mix(voice_path, "soft_piano.mp3")

        self.assertTrue(os.path.exists(out_path))


class VoiceCallServiceTests(TestCase):
    @mock.patch("voice_wishes.services.voice_call_service._get_client")
    @override_settings(VOICE_WISH_CALLER_ID="+256780000000")
    def test_place_call_returns_session_id(self, mock_get_client):
        mock_client = mock.Mock()
        mock_client.call.return_value = {"entries": [{"sessionId": "sess-123"}]}
        mock_get_client.return_value = mock_client

        session_id = voice_call_service.place_call("+256700000000")

        self.assertEqual(session_id, "sess-123")
        mock_client.call.assert_called_once_with(
            callFrom="+256780000000", callTo=["+256700000000"]
        )

    @mock.patch("voice_wishes.services.voice_call_service._get_client")
    def test_place_call_raises_if_no_session_id(self, mock_get_client):
        mock_client = mock.Mock()
        mock_client.call.return_value = {"entries": []}
        mock_get_client.return_value = mock_client

        with self.assertRaises(voice_call_service.VoiceCallError):
            voice_call_service.place_call("+256700000000")

    @mock.patch("voice_wishes.services.voice_call_service._get_client")
    def test_place_call_wraps_provider_errors(self, mock_get_client):
        mock_client = mock.Mock()
        mock_client.call.side_effect = RuntimeError("provider down")
        mock_get_client.return_value = mock_client

        with self.assertRaises(voice_call_service.VoiceCallError):
            voice_call_service.place_call("+256700000000")

    def test_build_play_and_hangup_response_only_contains_play(self):
        xml = voice_call_service.build_play_and_hangup_response("https://cdn.example.com/a.mp3")
        self.assertIn("<Play url=\"https://cdn.example.com/a.mp3\"/>", xml)
        self.assertNotIn("GetDigits", xml)
        self.assertNotIn("Record", xml)
