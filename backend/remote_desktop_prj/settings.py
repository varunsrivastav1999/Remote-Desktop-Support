"""
Django settings for Remote Desktop.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def env_bool(name, default=False):
    """Parse common truthy env values."""
    return os.getenv(name, str(default)).lower() in ('true', '1', 'yes', 'on')


def env_csv(name, default=''):
    """Parse a comma-separated env var into a clean list."""
    return [item.strip() for item in os.getenv(name, default).split(',') if item.strip()]

# ─── Base ────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'insecure-dev-key-change-in-production')
DEBUG = env_bool('DJANGO_DEBUG', True)
ALLOWED_HOSTS = env_csv('DJANGO_ALLOWED_HOSTS', '*')

# ─── Installed Apps ──────────────────────────────────────────
INSTALLED_APPS = [
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party
    'rest_framework',
    'corsheaders',
    'channels',
    # Local
    'signaling',
]

# ─── Middleware ──────────────────────────────────────────────
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'remote_desktop_prj.urls'

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

# ─── ASGI ────────────────────────────────────────────────────
ASGI_APPLICATION = 'remote_desktop_prj.asgi.application'

# ─── Database ────────────────────────────────────────────────
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('POSTGRES_DB', 'remote_desktop'),
        'USER': os.getenv('POSTGRES_USER', 'admin'),
        'PASSWORD': os.getenv('POSTGRES_PASSWORD', 'password'),
        'HOST': os.getenv('POSTGRES_HOST', 'db'),
        'PORT': os.getenv('POSTGRES_PORT', '5432'),
    }
}

# ─── Channels (Redis) ───────────────────────────────────────
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [os.getenv('REDIS_URL', 'redis://redis:6379/0')],
        },
    },
}

# ─── REST Framework ──────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
}

# ─── CORS ────────────────────────────────────────────────────
CORS_ALLOW_ALL_ORIGINS = env_bool('CORS_ALLOW_ALL_ORIGINS', DEBUG)
CORS_ALLOWED_ORIGINS = env_csv(
    'CORS_ALLOWED_ORIGINS',
    'http://localhost:5173,http://127.0.0.1:5173'
)
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = env_csv(
    'CSRF_TRUSTED_ORIGINS',
    'http://localhost:5173,http://127.0.0.1:5173',
)

# ─── Auth ────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ─── Internationalization ────────────────────────────────────
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# ─── Static files ────────────────────────────────────────────
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage',
    },
}

# ─── Default auto field ─────────────────────────────────────
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
