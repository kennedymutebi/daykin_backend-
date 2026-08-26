"""
Places outbound one-way voice calls via Africa's Talking Voice API and
builds the XML response used to instruct the call to play audio and hang up.

Deliberately only ever uses a passive <Play> action — never <GetDigits>,
<Record>, or anything else that listens to or captures the recipient. That
is what guarantees the call can't be "disrupted" by anything the recipient
says or presses.
"""
import logging

from django.conf import settings

logger = logging.getLogger(__name__)


class VoiceCallError(Exception):
    pass


def place_call(recipient_number: str) -> str:
    """Initiate the outbound call and return the provider's session id."""
    client = _get_client()
    try:
        response = client.call(
            callFrom=settings.VOICE_WISH_CALLER_ID,
            callTo=[recipient_number],
        )
    except Exception as exc:  # pragma: no cover - network/provider errors
        logger.exception("Voice call initiation failed")
        raise VoiceCallError(str(exc)) from exc

    session_id = _extract_session_id(response)
    if not session_id:
        raise VoiceCallError(f"No session id in provider response: {response!r}")
    return session_id


def build_play_and_hangup_response(audio_url: str) -> str:
    """
    XML instructing the call to play the wish audio then end. No
    GetDigits/Record/other listening action is ever included.
    """
    return f'<?xml version="1.0" encoding="UTF-8"?><Response><Play url="{audio_url}"/></Response>'


def _get_client():  # pragma: no cover - trivial factory, mocked in tests
    import africastalking

    africastalking.initialize(settings.AT_USERNAME, settings.AT_API_KEY)
    return africastalking.Voice


def _extract_session_id(response) -> str:
    try:
        return response["entries"][0]["sessionId"]
    except (KeyError, IndexError, TypeError):
        return ""
