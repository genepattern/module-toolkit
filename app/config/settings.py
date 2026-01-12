"""
Django settings for GenePattern Module Generator Web UI.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file (if it exists)
# This will not override existing environment variables
env_file = BASE_DIR / '.env'
if env_file.exists():
    load_dotenv(env_file)

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-change-me')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv('DEBUG', 'True').lower() in ('true', '1', 'yes')

ALLOWED_HOSTS = ['copilot.genepattern.org', 'localhost', '127.0.0.1']

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "https://copilot.genepattern.org:8250",
    "https://copilot.genepattern.org",
]

# Application definition
INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'generator',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# No database - using filesystem only
DATABASES = {}

# Password validation - not needed as we use custom auth
AUTH_PASSWORD_VALIDATORS = []

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Session settings (file-based since no database)
SESSION_ENGINE = 'django.contrib.sessions.backends.file'
SESSION_FILE_PATH = BASE_DIR / 'sessions'

# Create sessions directory if it doesn't exist
SESSION_FILE_PATH.mkdir(exist_ok=True)

# Custom settings for the generator app
MODULE_TOOLKIT_PATH = Path(os.getenv('MODULE_TOOLKIT_PATH', '/Users/tmtabor/workspace/module-toolkit'))
GENERATED_MODULES_DIR = MODULE_TOOLKIT_PATH / 'generated-modules'
MAX_RUNS_PER_USER = int(os.getenv('MAX_RUNS_PER_USER', '20'))

# User authentication from .env
def get_users():
    users_str = os.getenv('USERS', '')
    passwords_str = os.getenv('PASSWORDS', '')
    users = [u.strip() for u in users_str.split(',') if u.strip()]
    passwords = [p.strip() for p in passwords_str.split(',') if p.strip()]
    return dict(zip(users, passwords))

AUTH_USERS = get_users()
