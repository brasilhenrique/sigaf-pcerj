# ARQUIVO: sigaf_project/settings/development.py

from .base import *

# Chave secreta para o ambiente de desenvolvimento (não use esta em produção)
SECRET_KEY = 'django-insecure-!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!'

# ATENÇÃO: DEBUG = True apenas em desenvolvimento!
DEBUG = True

ALLOWED_HOSTS = []

# Banco de dados para desenvolvimento
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}