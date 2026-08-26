"""
Rewrites a raw user message into a short, warm, spoken-style wish using an
LLM. Kept provider-agnostic behind `rewrite_emotional` so the API underneath
(Anthropic/OpenAI/etc.) can change without touching callers.
"""
import logging

from django.conf import settings

logger = logging.getLogger(__name__)

DEFAULT_MAX_WORDS = 18

_SYSTEM_PROMPT = (
    "You rewrite short messages into warm, natural-sounding spoken wishes "
    "for a text-to-speech phone call. Rules: keep the core meaning and any "
    "names or facts in the original message; make the tone warm and "
    "emotional but natural to say aloud; no hashtags, emojis, or written-only "
    "punctuation like parentheses; output ONLY the rewritten wish text, "
    "nothing else."
)


class LLMServiceError(Exception):
    pass


def rewrite_emotional(raw_text: str, max_words: int = DEFAULT_MAX_WORDS) -> str:
    """
    Rewrite `raw_text` into a short, emotional, speakable wish capped at
    `max_words` words. Always runs the AI pass — never returns the raw text
    unmodified, even if the sender's original text was already warm.
    """
    if not raw_text or not raw_text.strip():
        raise LLMServiceError("raw_text is empty")

    client = _get_client()
    user_prompt = (
        f'Rewrite this into a spoken wish of at most {max_words} words: '
        f'"{raw_text.strip()}"'
    )

    try:
        response = client.messages.create(
            model=settings.VOICE_WISH_LLM_MODEL,
            max_tokens=120,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = _extract_text(response)
    except Exception as exc:  # pragma: no cover - network/provider errors
        logger.exception("LLM rewrite failed")
        raise LLMServiceError(str(exc)) from exc

    text = text.strip().strip('"')
    if not text:
        raise LLMServiceError("LLM returned empty text")
    return text


def _get_client():  # pragma: no cover - trivial factory, mocked in tests
    import anthropic

    return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


def _extract_text(response) -> str:
    """Pull the first text block out of an Anthropic-style response."""
    for block in getattr(response, "content", []):
        if getattr(block, "type", None) == "text":
            return block.text
    raise LLMServiceError("No text block in LLM response")
