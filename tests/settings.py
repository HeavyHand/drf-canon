from typing import Any

SECRET_KEY = 'drf-canon-tests'

INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.auth',
    'rest_framework',
    'tests',
]

DEFAULT_AUTO_FIELD = 'django.db.models.AutoField'

DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}

USE_TZ = True

REST_FRAMEWORK: dict[str, Any] = {
    'DEFAULT_AUTHENTICATION_CLASSES': [],
    'DEFAULT_PERMISSION_CLASSES': [],
    'DEFAULT_SCHEMA_CLASS': 'drf_canon.contrib.spectacular.AutoSchema',
}
