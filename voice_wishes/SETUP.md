# voice_wishes — setup

## 1. Copy the app in
Drop the `voice_wishes/` folder next to `api/` in `daykin_backend/`, so it sits
at `daykin_backend/voice_wishes/`.

## 2. daykin_backend/settings.py

Add to `INSTALLED_APPS`:
```python
INSTALLED_APPS = [
    ...
    "voice_wishes",
]
```

Add these settings (pull real values from `.env` via python-decouple, same
pattern as the rest of the project):
```python
from decouple import config

# LLM (text polishing)
ANTHROPIC_API_KEY = config("ANTHROPIC_API_KEY")
VOICE_WISH_LLM_MODEL = config("VOICE_WISH_LLM_MODEL", default="claude-sonnet-5")

# TTS
TTS_PROVIDER_URL = config("TTS_PROVIDER_URL")
TTS_PROVIDER_API_KEY = config("TTS_PROVIDER_API_KEY")
VOICE_WISH_TTS_VOICE = config("VOICE_WISH_TTS_VOICE", default="warm_female_1")

# Audio pipeline
VOICE_WISH_AUDIO_TMP_DIR = str(BASE_DIR / "tmp" / "voice_wishes")
VOICE_WISH_MUSIC_DIR = str(BASE_DIR / "media" / "music_tracks")

# Africa's Talking
AT_USERNAME = config("AT_USERNAME")
AT_API_KEY = config("AT_API_KEY")
VOICE_WISH_CALLER_ID = config("VOICE_WISH_CALLER_ID")  # your AT virtual/shortcode number
```

## 3. daykin_backend/urls.py
```python
urlpatterns = [
    ...
    path("api/voice-wishes/", include("voice_wishes.urls")),
]
```

## 4. requirements.txt — add
```
anthropic
africastalking
requests
```
(`ffmpeg`/`ffprobe` are system binaries, not pip packages — add
`RUN apt-get install -y ffmpeg` to the Dockerfile.)

## 5. Migrate
```
python manage.py makemigrations voice_wishes  # only if you change models further
python manage.py migrate
```

## 6. Celery worker
Uses the project's existing Celery app (`daykin_backend/celery.py`) — no new
worker service is required to run it, though a dedicated queue/worker for
this app is worth adding once volume grows (see docker-compose note below).

Optional `docker-compose.yml` addition, once you want to isolate this
pipeline's worker (ffmpeg-heavy) from your main API's Celery worker:
```yaml
  celery-voice-wishes:
    build: .
    command: celery -A daykin_backend worker -Q voice_wishes -l info
    depends_on:
      - redis
      - db
    env_file: .env
```

## 7. Africa's Talking dashboard
Point your Voice application's callback URLs to:
- Voice callback (on call connect): `https://<your-domain>/api/voice-wishes/callbacks/voice/`
- Call status (on call end): `https://<your-domain>/api/voice-wishes/callbacks/voice/status/`

## 8. Run the tests
```
python manage.py test voice_wishes
```
Covers: model validation, serializer validation, each service function
(LLM, TTS, audio mixer, voice call — external calls mocked), each Celery
task in isolation (success/failure/retry-shrink paths), the API views
(create/status/webhooks), and a full end-to-end pipeline integration test
that runs create → polish → tts → mix → call → callback → status webhook
with only the true external I/O boundaries mocked.
