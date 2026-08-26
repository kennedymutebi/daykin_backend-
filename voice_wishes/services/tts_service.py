"""
Converts text into spoken audio files. Provider-agnostic wrapper — swap the
implementation of `_synthesize_to_file` to change TTS vendors without
touching callers.
"""
import logging
import os
import uuid

from django.conf import settings

logger = logging.getLogger(__name__)


class TTSServiceError(Exception):
    pass


def synthesize_wish(intro: str, message: str, outro: str) -> str:
    """
    Synthesize the full spoken wish (intro + message + outro) as ONE audio
    file so pacing/pauses between the parts sound natural, and return the
    local file path.
    """
    full_script = " ... ".join(part.strip() for part in (intro, message, outro) if part.strip())
    if not full_script:
        raise TTSServiceError("Nothing to synthesize")

    out_dir = settings.VOICE_WISH_AUDIO_TMP_DIR
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"voice_{uuid.uuid4().hex}.mp3")

    try:
        _synthesize_to_file(full_script, out_path)
    except Exception as exc:  # pragma: no cover - network/provider errors
        logger.exception("TTS synthesis failed")
        raise TTSServiceError(str(exc)) from exc

    if not os.path.exists(out_path):
        raise TTSServiceError("TTS provider did not produce an output file")
    return out_path


def _synthesize_to_file(text: str, out_path: str) -> None:  # pragma: no cover
    """Thin wrapper around the actual TTS provider SDK/HTTP call."""
    import requests

    resp = requests.post(
        settings.TTS_PROVIDER_URL,
        headers={"Authorization": f"Bearer {settings.TTS_PROVIDER_API_KEY}"},
        json={"text": text, "voice": settings.VOICE_WISH_TTS_VOICE},
        timeout=30,
    )
    resp.raise_for_status()
    with open(out_path, "wb") as f:
        f.write(resp.content)
