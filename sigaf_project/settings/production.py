# ARQUIVO: sigaf_project/settings/production.py

from .base import *
import os
import dj_database_url

# Configurações para o ambiente de PRODUÇÃO (DigitalOcean)
DEBUG = False

# A SECRET_KEY será lida de uma variável de ambiente no servidor
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'uma-chave-padrao-de-seguranca-caso-a-variavel-nao-esteja-setada')

# Adicione o IP do seu servidor aqui
ALLOWED_HOSTS = ['167.172.137.159']

# Configuração do banco de dados PostgreSQL
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'sigaf_db',
        'USER': 'sigaf_user',
        'PASSWORD': 'mKfL%5f3qL', # <-- ATENÇÃO: COLOQUE A SENHA QUE VOCÊ CRIOU AQUI
        'HOST': 'localhost', # O banco está no mesmo servidor que a aplicação
        'PORT': '5432',
    }
}

# --- Configuração do WhiteNoise para Arquivos Estáticos ---

# Adiciona o middleware do WhiteNoise. A posição é importante: logo após o SecurityMiddleware.
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

# Caminho onde o `collectstatic` irá juntar todos os arquivos estáticos
STATIC_ROOT = BASE_DIR / "staticfiles"

# Define o backend de armazenamento para o WhiteNoise
STORAGES = {
    "staticfiles": {
        # ALTERAÇÃO FINAL: Trocamos para uma versão menos rigorosa do WhiteNoise
        # que não valida os sourcemaps e links internos dos arquivos CSS.
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}