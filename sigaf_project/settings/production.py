# ARQUIVO: sigaf_project/settings/production.py

from .base import *
import os
import dj_database_url

# Configurações para o ambiente de PRODUÇÃO
DEBUG = False

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')

# O Render define o hostname automaticamente
RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS = [RENDER_EXTERNAL_HOSTNAME]
else:
    ALLOWED_HOSTS = []

# Configuração do banco de dados PostgreSQL do Render
DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get('DATABASE_URL'),
        conn_max_age=600
    )
}

# --- INÍCIO DA ALTERAÇÃO WHITENOISE ---

# Adiciona o middleware do WhiteNoise. A posição é importante: logo após o SecurityMiddleware.
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

# Configuração para arquivos estáticos em produção
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Configuração do armazenamento do WhiteNoise
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# --- FIM DA ALTERAÇÃO WHITENOISE ---