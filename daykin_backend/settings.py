from pathlib import Path
from datetime import timedelta
from decouple import config, Csv

from celery.schedules import crontab
# ...other imports...

BASE_DIR = Path(__file__).resolve().parent.parent

# ── Core ────────────────────────────────────────────────────────────────────
SECRET_KEY = config('SECRET_KEY', default='django-insecure-change-this-in-production-use-env-variable')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='*', cast=Csv())

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'django_filters',
    'drf_spectacular',
    # Local
    'api',
    'voice_wishes',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'daykin_backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'daykin_backend.wsgi.application'

# ── Database ────────────────────────────────────────────────────────────────
# HOST defaults to the docker-compose service name for the MySQL container.
# Override via .env for local (non-Docker) development, e.g. HOST=localhost
RUNNING_IN_DOCKER = config('RUNNING_IN_DOCKER', default=False, cast=bool)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': 'daykin_db' if RUNNING_IN_DOCKER else '127.0.0.1',
        'PORT': '3306' if RUNNING_IN_DOCKER else '3306',
    }
}
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Kampala'
USE_I18N = True
USE_TZ = True

# ── Static / Media ──────────────────────────────────────────────────────────
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = config('MEDIA_URL', default='/media/')
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── Django REST Framework ──────────────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_THROTTLE_RATES': {
        # ...any existing scopes...
        'presence_ping': '20/min',
    },
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# ── JWT ────────────────────────────────────────────────────────────────────
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=12),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
}

# ── CORS ────────────────────────────────────────────────────────────────────
# Includes local dev origins plus the production frontend (VPS IP:3006).
# Add more origins via the CORS_sjKNFML,LS,;,EXTRA_ORIGINS env var (comma-separated) if needed.
CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default='http://localhost:5173,http://127.0.0.1:4200,http://84.247.171.71:3006',
    cast=Csv(),
)
CORS_ALLOW_CREDENTIALS = True


CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='redis://daykin_redis:6379/0')
CELERY_RESULT_BACKEND = config('CELERY_BROKER_URL', default='redis://daykin_redis:6379/0')
CELERY_BEAT_SCHEDULE = {
    'process-birthday-celebrations-hourly': {
        'task': 'api.tasks.process_birthday_celebrations',   # was 'celebrations.tasks...'
        'schedule': crontab(minute=0),
    },
}

# ── Swagger / OpenAPI (drf-spectacular) ────────────────────────────────────
SPECTACULAR_SETTINGS = {
    'TITLE': 'Daykin API',
    'DESCRIPTION': (
        'REST API for the Daykin celebrity & entertainment platform.\n\n'
        '**Admin-only endpoints** (require staff JWT): celebrities (write), articles (write), charities (write).\n\n'
        'To authenticate: call `/api/auth/login/`, copy the `access` token, '
        'click **Authorize** and enter `Bearer <token>`.'
    ),
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'CONTACT': {'name': 'Daykin Dev', 'email': 'dev@daykin.com'},
    'TAGS': [
        {'name': 'auth',         'description': 'Register, login and token management'},
        {'name': 'celebrities',  'description': 'Celebrity profiles and birthdays'},
        {'name': 'articles',     'description': 'News and editorial articles (Admin: write)'},
        {'name': 'posts',        'description': 'User-generated feed posts'},
        {'name': 'charities',    'description': 'Charity campaigns (Admin: write)'},
        {'name': 'love-stories', 'description': 'Community love stories'},
    ],
    'COMPONENT_SPLIT_REQUEST': True,
    'SCHEMA_PATH_PREFIX': '/api/',
}
# ── Voice Wishes ────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = config('ANTHROPIC_API_KEY')
VOICE_WISH_LLM_MODEL = config('VOICE_WISH_LLM_MODEL', default='claude-sonnet-5')

TTS_PROVIDER_URL = config('TTS_PROVIDER_URL')
TTS_PROVIDER_API_KEY = config('TTS_PROVIDER_API_KEY')
VOICE_WISH_TTS_VOICE = config('VOICE_WISH_TTS_VOICE', default='warm_female_1')

VOICE_WISH_AUDIO_TMP_DIR = str(BASE_DIR / 'tmp' / 'voice_wishes')
VOICE_WISH_MUSIC_DIR = str(BASE_DIR / 'media' / 'music_tracks')

AT_USERNAME = config('AT_USERNAME')
AT_API_KEY = config('AT_API_KEY')
VOICE_WISH_CALLER_ID = config('VOICE_WISH_CALLER_ID')