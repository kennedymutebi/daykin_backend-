from io import BytesIO
from gtts import gTTS
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile


def generate_article_audio(article_id: int) -> bool:
    """
    Convert article title + content to MP3 using gTTS.
    Uses queryset .update() to save the path so it does NOT
    re-trigger the post_save signal (avoids infinite loop).
    Returns True on success, False on failure.
    """
    # Import inside function — safe for use in threads / signals
    from .models import Article

    try:
        article = Article.objects.get(pk=article_id)
        text = f"{article.title}. {article.content}"

        tts = gTTS(text=text, lang='en', slow=False)

        buffer = BytesIO()
        tts.write_to_fp(buffer)
        buffer.seek(0)

        filepath = f"articles/audio/article_{article_id}.mp3"

        # Delete old audio file if it exists
        if article.audio and default_storage.exists(article.audio.name):
            default_storage.delete(article.audio.name)

        # Save new MP3 to storage
        saved_path = default_storage.save(filepath, ContentFile(buffer.read()))

        # Update DB without triggering post_save signal
        Article.objects.filter(pk=article_id).update(audio=saved_path)
        return True

    except Exception as e:
        print(f"[TTS] Audio generation failed for article {article_id}: {e}")
        return False