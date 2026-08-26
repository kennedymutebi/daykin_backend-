import logging

from celery import shared_task
from django.conf import settings

from .models import MAX_CALL_DURATION_SECONDS, MAX_POLISH_RETRIES, VoiceWish
from .services import audio_mixer, llm_service, tts_service, voice_call_service

logger = logging.getLogger(__name__)

INITIAL_MAX_WORDS = 18
WORDS_SHRINK_PER_RETRY = 4


@shared_task(bind=True, max_retries=2)
def polish_text(self, wish_id, max_words=INITIAL_MAX_WORDS):
    try:
        wish = VoiceWish.objects.get(id=wish_id)
    except VoiceWish.DoesNotExist:
        logger.warning("polish_text: VoiceWish %s not found", wish_id)
        return

    try:
        wish.polished_text = llm_service.rewrite_emotional(wish.raw_text, max_words)
    except llm_service.LLMServiceError as exc:
        wish.mark_failed(f"polish_failed: {exc}")
        return

    wish.status = VoiceWish.Status.POLISHING
    wish.save(update_fields=["polished_text", "status", "updated_at"])
    generate_audio.delay(str(wish.id))


@shared_task(bind=True, max_retries=2)
def generate_audio(self, wish_id):
    try:
        wish = VoiceWish.objects.get(id=wish_id)
    except VoiceWish.DoesNotExist:
        logger.warning("generate_audio: VoiceWish %s not found", wish_id)
        return

    try:
        voice_path = tts_service.synthesize_wish(
            intro=f"A wish for you from {wish.sender_name}",
            message=wish.polished_text,
            outro="Sent via Daykin",
        )
        duration = audio_mixer.get_duration(voice_path)
    except (tts_service.TTSServiceError, audio_mixer.AudioMixerError) as exc:
        wish.mark_failed(f"audio_generation_failed: {exc}")
        return

    if duration > MAX_CALL_DURATION_SECONDS and wish.retry_count < MAX_POLISH_RETRIES:
        wish.retry_count += 1
        wish.save(update_fields=["retry_count", "updated_at"])
        shrunk_max_words = max(6, INITIAL_MAX_WORDS - (wish.retry_count * WORDS_SHRINK_PER_RETRY))
        polish_text.delay(str(wish.id), max_words=shrunk_max_words)
        return

    if duration > MAX_CALL_DURATION_SECONDS:
        wish.mark_failed("audio_too_long_after_retries")
        return

    wish.voice_audio_path = voice_path
    wish.status = VoiceWish.Status.GENERATING_AUDIO
    wish.save(update_fields=["voice_audio_path", "status", "updated_at"])
    mix_audio.delay(str(wish.id))


@shared_task(bind=True, max_retries=2)
def mix_audio(self, wish_id):
    try:
        wish = VoiceWish.objects.get(id=wish_id)
    except VoiceWish.DoesNotExist:
        logger.warning("mix_audio: VoiceWish %s not found", wish_id)
        return

    try:
        final_path = audio_mixer.mix(wish.voice_audio_path, wish.music_track)
        final_url = audio_mixer.upload_public(final_path)
        duration = audio_mixer.get_duration(final_path)
    except audio_mixer.AudioMixerError as exc:
        wish.mark_failed(f"mixing_failed: {exc}")
        return

    wish.final_audio_url = final_url
    wish.audio_duration_seconds = duration
    wish.status = VoiceWish.Status.MIXING
    wish.save(update_fields=["final_audio_url", "audio_duration_seconds", "status", "updated_at"])
    place_call.delay(str(wish.id))


@shared_task(bind=True, max_retries=2)
def place_call(self, wish_id):
    try:
        wish = VoiceWish.objects.get(id=wish_id)
    except VoiceWish.DoesNotExist:
        logger.warning("place_call: VoiceWish %s not found", wish_id)
        return

    if not wish.final_audio_url:
        wish.mark_failed("missing_final_audio_url")
        return

    try:
        session_id = voice_call_service.place_call(wish.recipient_number)
    except voice_call_service.VoiceCallError as exc:
        wish.mark_failed(f"call_failed: {exc}")
        return

    wish.call_session_id = session_id
    wish.status = VoiceWish.Status.CALLING
    wish.save(update_fields=["call_session_id", "status", "updated_at"])
