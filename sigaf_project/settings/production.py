# ARQUIVO: sigaf_project/settings/production.py

from .base import *
import os

# Configurações para o ambiente de PRODUÇÃO (DigitalOcean)
DEBUG = False

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'uma-chave-padrao-de-seguranca-caso-a-variavel-nao-esteja-setada')

# Hosts permitidos
ALLOWED_HOSTS = ['henriquebrasil.com.br', 'www.henriquebrasil.com.br', '167.172.137.159']

# Configuração do banco de dados PostgreSQL
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'sigaf_db',
        'USER': 'sigaf_user',
        'PASSWORD': 'a_senha_forte_que_voce_anotou', # <-- ATENÇÃO: COLOQUE A SENHA CORRETA AQUI
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

# Configuração do WhiteNoise para Arquivos Estáticos
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

# --- CONFIGURAÇÃO DO LOGOFF AUTOMÁTICO POR INATIVIDADE ---
# Tempo da sessão em segundos (60 minutos * 60 segundos = 3600)
SESSION_COOKIE_AGE = 3600

# Salva a sessão a cada requisição, resetando o timer de inatividade
SESSION_SAVE_EVERY_REQUEST = True